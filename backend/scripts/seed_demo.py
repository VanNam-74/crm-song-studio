"""Seed realistic demo data for UI work (one fake site "demo", orders DEMO-1001...).

    python -m scripts.seed_demo            # create (skips if demo data exists)
    python -m scripts.seed_demo --reset    # delete demo data, then create again
    python -m scripts.seed_demo --delete   # only delete demo data

Everything belongs to the site with slug "demo", so real orders are never touched.
Audio files are NOT uploaded: clips only have placeholder R2 keys.
"""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select, update

from app.core.db import SessionLocal, engine
from app.core.security import encrypt, new_secret
from app.models import (
    AdminUser, DeliveryOption, EventLevel, GenerationStatus, JobEvent, JobStatus, JobType,
    LyricGeneration, LyricsStatus, MusicClip, MusicGeneration, MusicProviderType, OrderStatus,
    PromptTemplate, PromptVersion, ProviderConfig, Site, SongJob, SongOrder, UserRole,
)

DEMO_SLUG = "demo"
DEMO_PROVIDER = "Demo · Suno cookie"
DEMO_BUCKET = "demo-bucket"
NOW = datetime.now(timezone.utc)

SYSTEM_PROMPT = (
    "You are a professional songwriter who writes personalised songs for real families.\n"
    "Write lyrics that sound natural when sung, with [Verse], [Pre-Chorus], [Chorus], [Bridge] and [Outro] tags.\n"
    "Use every name and memory the customer marked as required. Never mention real artists.\n"
    "The style field must describe genre, mood, instruments, vocal and tempo only."
)
USER_TEMPLATE = (
    "Write a {{ occasion }} song for {{ recipient_name }} ({{ relationship }}), a gift from {{ sender_name }}.\n"
    "Genre: {{ genre }} · Voice: {{ voice }} · Mood: {{ mood }}\n"
    "Must include: {{ must_include | join(', ') }}\n\nTheir story:\n{{ story }}"
)

LYRICS = {
    "forty": (
        "[Verse 1]\nBack in '85 on the Tahoe shore\nYou wore that yellow dress I still adore\n"
        "You laughed at every joke I didn't land\nAnd Maggie, that's the night I took your hand\n\n"
        "[Pre-Chorus]\nForty winters later, side by side\nYou're still the reason I feel alive\n\n"
        "[Chorus]\nForty years of you, forty years of light\nEvery ordinary morning turned out right\n"
        "Through the storms and the quiet afternoons\nI'd choose it all again — forty years of you\n\n"
        "[Verse 2]\nThree small coats by the door on Maple Row\nSunday kitchen dancing to the radio\n"
        "When the hardest year came knocking on our door\nYou held us steady, and I loved you more\n\n"
        "[Outro]\nSo dance with me, the radio's still on\nForty years of you — and forty more to come"
    ),
    "star": (
        "[Verse 1]\nSix candles on a cake of pink and gold\nA brand-new bike, a story to be told\n"
        "You count the stars from your window every night\nAnd, Lily, you're the one that shines so bright\n\n"
        "[Chorus]\nLittle star, big heart, you light up every room\nLittle star, big heart, you make the flowers bloom\n"
        "Wherever you go, whatever you do\nThe whole wide sky is cheering for you\n\n"
        "[Outro]\nHappy birthday, little star"
    ),
    "generic": (
        "[Verse 1]\nThere's a light in the window when you come home\nA song in the kitchen we've always known\n\n"
        "[Chorus]\nThis one's for you, for all that you do\nEvery small moment I'm thankful for you\n\n"
        "[Outro]\nThis one's for you"
    ),
    "pages_v0": (
        "[Verse 1]\nI still remember that April afternoon\nAmong the roses in your mother's garden bloom\n"
        "You handed me a daisy, said keep this one\nAnd something in my chest came undone\n\n"
        "[Chorus]\nYou and me, we're the pages of us\nEvery chapter written in trust\n"
        "From the garden gate to the life we made\nYou're my favorite story, page by page"
    ),
    "pages_v1": (
        "[Verse 1]\nI still remember that April afternoon\nA little bookstore down on 5th Street, half past two\n"
        "You reached for the same worn paperback as me\nAnd something in my chest came undone\n\n"
        "[Chorus]\nYou and me, we're the pages of us\nEvery chapter written in trust\n"
        "From that dusty shelf to the life we made\nYou're my favorite story, page by page"
    ),
}

# order_no, title, customer, recipient, relationship, occasion, genre, voice, package, paid hours ago, scenario
ORDERS = [
    (1001, "Forty Years of You", "Daniel W.", "Margaret", "Wife", "40th anniversary", "Acoustic folk", "Warm male", "1_day", 18.5, "lyrics_review"),
    (1002, "Little Star, Big Heart", "Hannah L.", "Lily", "Daughter", "6th birthday", "Acoustic pop", "Gentle female", "1_day", 13, "pick_take"),
    (1003, "Home Is You", "Olivia K.", "Mom", "Mother", "Mother's birthday", "Soft piano ballad", "Warm female", "3_day", 15, "generating_music"),
    (1004, "The Road We Took", "James P.", "Michael", "Brother", "Wedding", "Country", "Male", "1_day", 21, "ready"),
    (1005, "Golden Years", "Robert H.", "Mom & Dad", "Parents", "50th anniversary", "Classic soul", "Male", "3_day", 80, "done"),
    (1006, "Sunday Pancakes", "Priya S.", "Dad", "Father", "Father's birthday", "Indie folk", "Female", "3_day", 20, "failed"),
    (1007, "Grandpa's Garden", "Mei C.", "Grandpa Lin", "Grandfather", "80th birthday", "Acoustic", "Male", "3_day", 0.2, "queued"),
    (1008, "Pages of Us", "Marcus T.", "Jordan", "Partner", "Anniversary", "Acoustic pop", "Warm male", "1_day", 50, "revision"),
    (1009, "My Best Friend Max", "Ava D.", "Max", "Dog", "Gotcha day", "Playful pop", "Female", "1_day", 27, "overdue"),
]


def ago(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)


def snapshot(order_no, title, customer, recipient, rel, occasion, genre, voice, package, paid_at) -> dict:
    return {
        "id": 900000 + order_no,
        "number": f"DEMO-{order_no}",
        "status": "processing",
        "paid_at": paid_at.isoformat(),
        "currency": "USD",
        "total": "99.00" if package == "3_day" else "129.00",
        "customer": {"name": customer, "email": f"demo{order_no}@example.com"},
        "package": f"Custom Song – {'Express' if package == '1_day' else 'Standard'}",
        "delivery_option": package,
        "items": [{"product_id": 1, "name": "Custom Song", "quantity": 1,
                   "meta": {"Delivery": "1 Day" if package == "1_day" else "3 Days"}}],
        "story": {
            "tnm_recipient_name": recipient,
            "tnm_sender_name": customer.split(" ")[0],
            "tnm_relationship": rel,
            "tnm_occasion": occasion,
            "tnm_genre": genre,
            "tnm_voice": voice,
            "tnm_mood": "Tender, grateful",
            "tnm_must_include": [recipient],
            "tnm_story": f"[Demo] A short story about {recipient} for the song \"{title}\".",
        },
    }


async def delete_demo(session) -> bool:
    site = await session.scalar(select(Site).where(Site.slug == DEMO_SLUG))
    if site is None:
        return False
    job_ids = select(SongJob.id).where(SongJob.site_id == site.id)
    gen_ids = select(MusicGeneration.id).where(MusicGeneration.job_id.in_(job_ids))

    await session.execute(update(SongOrder).where(SongOrder.site_id == site.id).values(current_job_id=None))
    await session.execute(update(SongJob).where(SongJob.site_id == site.id).values(selected_clip_id=None, parent_job_id=None))
    await session.execute(delete(MusicClip).where(MusicClip.generation_id.in_(gen_ids)))
    await session.execute(delete(MusicGeneration).where(MusicGeneration.job_id.in_(job_ids)))
    await session.execute(delete(LyricGeneration).where(LyricGeneration.job_id.in_(job_ids)))
    await session.execute(delete(JobEvent).where(JobEvent.job_id.in_(job_ids)))
    await session.execute(delete(SongJob).where(SongJob.site_id == site.id))
    await session.execute(delete(SongOrder).where(SongOrder.site_id == site.id))

    tpl_ids = select(PromptTemplate.id).where(PromptTemplate.site_id == site.id)
    await session.execute(update(PromptTemplate).where(PromptTemplate.site_id == site.id).values(active_version_id=None))
    await session.execute(delete(PromptVersion).where(PromptVersion.template_id.in_(tpl_ids)))
    await session.execute(delete(PromptTemplate).where(PromptTemplate.site_id == site.id))
    await session.execute(delete(Site).where(Site.id == site.id))
    await session.execute(delete(ProviderConfig).where(ProviderConfig.name == DEMO_PROVIDER))
    await session.commit()
    return True


async def create_demo(session) -> None:
    admin = await session.scalar(select(AdminUser).where(AdminUser.role == UserRole.ADMIN).order_by(AdminUser.id))
    admin_id = admin.id if admin else None

    provider = ProviderConfig(name=DEMO_PROVIDER, type=MusicProviderType.SUNO_COOKIE, max_concurrent=1,
                              max_per_hour=12, last_health_check_at=ago(0.05), last_health_status="ok",
                              credits_remaining=412)
    site = Site(name="Demo site", slug=DEMO_SLUG, base_url="https://demo.example.com",
                webhook_secret_enc=encrypt(new_secret()), r2_prefix="demo/songs/")
    session.add_all([provider, site])
    await session.flush()

    tpl = PromptTemplate(site_id=site.id, name="Song – initial (demo)", description="Demo template")
    session.add(tpl)
    await session.flush()
    versions = []
    for v, note in [(1, "First version"), (2, "Style field: no artist names"), (3, "Require every must_include name")]:
        pv = PromptVersion(template_id=tpl.id, version=v, system_prompt=SYSTEM_PROMPT, user_template=USER_TEMPLATE,
                           model="gpt-5.5", model_params={"reasoning_effort": "medium"}, change_note=note,
                           created_by_id=admin_id)
        session.add(pv)
        versions.append(pv)
    await session.flush()
    tpl.active_version_id = versions[-1].id
    site.default_prompt_template_id = tpl.id
    site.provider_config_id = provider.id
    pv_id = versions[-1].id

    def event(job, step, message, hours_ago, level=EventLevel.INFO, actor=None, data=None):
        session.add(JobEvent(job_id=job.id, step=step, message=message, level=level,
                             actor_id=actor, data=data, created_at=ago(hours_ago)))

    def lyric_gen(job, key, title, style, hours_ago, cost="0.0120"):
        session.add(LyricGeneration(
            job_id=job.id, prompt_version_id=pv_id, model="gpt-5.5",
            rendered_prompt=f"[demo rendered prompt for {title}]", status=GenerationStatus.COMPLETE,
            title=title, style=style, lyrics=LYRICS[key], input_tokens=640, output_tokens=644,
            cost=Decimal(cost), duration_ms=6200, created_at=ago(hours_ago)))

    async def music(job, order_no, rev, title, style, hours_ago, complete=True):
        gen = MusicGeneration(
            job_id=job.id, provider_config_id=provider.id, provider_type=MusicProviderType.SUNO_COOKIE,
            request_payload={"title": title, "style": style, "lyrics_chars": 1048},
            status=GenerationStatus.COMPLETE if complete else GenerationStatus.PENDING,
            poll_count=14 if complete else 5, cost=Decimal("0.0600") if complete else None,
            submitted_at=ago(hours_ago), completed_at=ago(hours_ago - 0.2) if complete else None)
        session.add(gen)
        await session.flush()
        clips = []
        if complete:
            for letter, dur, size in [("A", "161.40", 3_900_000), ("B", "178.20", 4_300_000)]:
                clip = MusicClip(
                    generation_id=gen.id, provider_clip_id=f"demo-{order_no}-{rev}-{letter.lower()}",
                    status=GenerationStatus.COMPLETE, duration_sec=Decimal(dur), r2_bucket=DEMO_BUCKET,
                    r2_key=f"demo/songs/DEMO-{order_no}/rev-{rev}/take-{letter}.mp3",
                    file_size=size, mime_type="audio/mpeg", provider_meta={"model": "v6"})
                session.add(clip)
                clips.append(clip)
            await session.flush()
        return clips

    for (order_no, title, customer, recipient, rel, occasion, genre, voice, package, paid_h, scenario) in ORDERS:
        paid_at = ago(paid_h)
        option = DeliveryOption(package)
        hours = 24 if option is DeliveryOption.ONE_DAY else 72
        style = f"{genre.lower()}, {voice.lower()} vocal, warm, 92 bpm"
        snap = snapshot(order_no, title, customer, recipient, rel, occasion, genre, voice, package, paid_at)

        order = SongOrder(site_id=site.id, wp_order_id=900000 + order_no, order_number=f"DEMO-{order_no}",
                          customer_name=customer, customer_email=f"demo{order_no}@example.com",
                          package_name=snap["package"], delivery_option=option, paid_at=paid_at,
                          status=OrderStatus.DONE if scenario == "done" else OrderStatus.ACTIVE)
        session.add(order)
        await session.flush()

        job = SongJob(order_id=order.id, site_id=site.id, revision_no=0, job_type=JobType.INITIAL,
                      priority=9 if option is DeliveryOption.ONE_DAY else 5,
                      due_at=paid_at + timedelta(hours=hours), input_snapshot=snap,
                      status=JobStatus.QUEUED, cost_openai=Decimal("0"), cost_music=Decimal("0"))
        session.add(job)
        await session.flush()
        order.current_job_id = job.id

        event(job, "webhook", f"Order #DEMO-{order_no} received ({package.replace('_', '-')} package)", paid_h)
        event(job, "fetch_order", "Order data captured from webhook", paid_h - 0.01)
        if scenario == "queued":
            continue

        key = "forty" if order_no == 1001 else "star" if order_no == 1002 else "pages_v0" if order_no == 1008 else "generic"
        lyric_gen(job, key, title, style, paid_h - 0.03)
        event(job, "gen_lyrics", "Draft 1 generated · Song – initial v3", paid_h - 0.03)
        job.final_title, job.final_style, job.final_lyrics = title, style, LYRICS[key]
        job.lyrics_status = LyricsStatus.DRAFT
        job.cost_openai = Decimal("0.0120")

        if scenario in ("lyrics_review", "overdue"):
            if scenario == "lyrics_review":
                lyric_gen(job, key, title, style, paid_h - 0.05, cost="0.0130")
                event(job, "gen_lyrics", "Draft 2 generated · Song – initial v3", paid_h - 0.05)
                event(job, "review", "Admin edited 2 lines", paid_h - 0.2, actor=admin_id)
                job.lyrics_status = LyricsStatus.EDITED
                job.cost_openai = Decimal("0.0250")
            job.status = JobStatus.LYRICS_READY
            continue

        job.lyrics_status = LyricsStatus.APPROVED
        job.lyrics_approved_by_id = admin_id
        job.lyrics_approved_at = ago(paid_h - 0.3)
        event(job, "review", "Lyrics approved", paid_h - 0.3, actor=admin_id)
        event(job, "submit_music", "Sent to Demo · Suno cookie", paid_h - 0.32)

        if scenario == "failed":
            job.status = JobStatus.FAILED
            job.error_step = "submit_music"
            job.error_message = "403 captcha_required (5/5 attempts)"
            job.retry_count = 5
            for i in range(1, 5):
                event(job, "submit_music", f"Attempt {i}/5 failed: 403 captcha_required", paid_h - 0.32 - i * 0.05, level=EventLevel.WARNING)
            event(job, "submit_music", "Attempt 5/5 failed: 403 captcha_required. Job marked failed.", paid_h - 0.6, level=EventLevel.ERROR)
            continue

        if scenario == "generating_music":
            await music(job, order_no, 0, title, style, 0.05, complete=False)
            job.status = JobStatus.GENERATING_MUSIC
            continue

        clips = await music(job, order_no, 0, title, style, paid_h - 0.35)
        job.cost_music = Decimal("0.0600")
        event(job, "upload", "Both takes saved to R2", paid_h - 0.55)

        if scenario == "pick_take":
            job.status = JobStatus.MUSIC_READY
            continue

        job.selected_clip_id = clips[1].id
        event(job, "select", "Take B selected as final", paid_h - 0.7, actor=admin_id)

        if scenario == "ready":
            job.status = JobStatus.READY
            continue

        job.status = JobStatus.DONE
        job.done_at = ago(paid_h - 1)
        job.done_by_id = admin_id
        event(job, "done", "Lyrics and file copied to HIS CRM", paid_h - 1, actor=admin_id)

        if scenario == "revision":
            rev = SongJob(order_id=order.id, site_id=site.id, revision_no=1, job_type=JobType.REVISION_LYRICS,
                          parent_job_id=job.id, priority=9, due_at=ago(2) + timedelta(hours=24),
                          customer_feedback=("We love it! Could you change the line about the garden — we actually met "
                                             "in a little bookstore on 5th Street. And maybe make it a bit more upbeat?"),
                          input_snapshot=snap, status=JobStatus.LYRICS_READY, lyrics_status=LyricsStatus.DRAFT,
                          final_title=title, final_style="upbeat acoustic pop, warm male vocal, piano, 112 bpm",
                          final_lyrics=LYRICS["pages_v1"], cost_openai=Decimal("0.0110"), cost_music=Decimal("0"))
            session.add(rev)
            await session.flush()
            order.current_job_id = rev.id
            event(rev, "webhook", "Revision #1 requested by customer", 2)
            lyric_gen(rev, "pages_v1", title, rev.final_style, 1.9, cost="0.0110")
            event(rev, "gen_lyrics", "Revision draft generated · Song – revision v2", 1.9)

    await session.commit()


async def main(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        if args.reset or args.delete:
            removed = await delete_demo(session)
            print("Demo data deleted." if removed else "No demo data to delete.")
            if args.delete:
                await engine.dispose()
                return
        exists = await session.scalar(select(Site.id).where(Site.slug == DEMO_SLUG))
        if exists:
            print("Demo data already exists. Use --reset to recreate it.")
        else:
            await create_demo(session)
            print(f"Created demo site '{DEMO_SLUG}' with {len(ORDERS)} orders (DEMO-1001 … DEMO-{ORDERS[-1][0]}).")
    await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="delete demo data and create it again")
    p.add_argument("--delete", action="store_true", help="only delete demo data")
    asyncio.run(main(p.parse_args()))