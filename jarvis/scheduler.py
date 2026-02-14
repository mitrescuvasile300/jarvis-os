"""Jarvis Scheduler — cron job runner for automated tasks.

Reads cron definitions from config/crons.yml and executes
skill actions on schedule.
"""

import asyncio
import logging
import signal
from datetime import datetime

from jarvis.agent import JarvisAgent
from jarvis.config import load_config

logger = logging.getLogger("jarvis.scheduler")


class CronJob:
    def __init__(self, name: str, schedule: str, skill: str, action: str, params: dict):
        self.name = name
        self.schedule = schedule
        self.skill = skill
        self.action = action
        self.params = params
        self.last_run: datetime | None = None

    def should_run(self, now: datetime) -> bool:
        """Check if the job should run based on cron schedule."""
        parts = self.schedule.split()
        if len(parts) != 5:
            return False

        minute, hour, dom, month, dow = parts

        if not self._matches(minute, now.minute):
            return False
        if not self._matches(hour, now.hour):
            return False
        if not self._matches(dom, now.day):
            return False
        if not self._matches(month, now.month):
            return False
        if not self._matches(dow, now.weekday()):
            return False

        # Don't run more than once per minute
        if self.last_run and (now - self.last_run).total_seconds() < 60:
            return False

        return True

    @staticmethod
    def _matches(pattern: str, value: int) -> bool:
        """Check if a cron field pattern matches a value."""
        if pattern == "*":
            return True

        # Handle */N (every N)
        if pattern.startswith("*/"):
            step = int(pattern[2:])
            return value % step == 0

        # Handle comma-separated values
        if "," in pattern:
            return value in [int(v) for v in pattern.split(",")]

        # Handle ranges (e.g., 1-5)
        if "-" in pattern:
            start, end = pattern.split("-")
            return int(start) <= value <= int(end)

        # Exact match
        return value == int(pattern)


class JarvisScheduler:
    def __init__(self):
        self.config = load_config()
        self.agent = JarvisAgent(self.config)
        self.jobs: list[CronJob] = []

    def _load_jobs(self):
        """Load cron jobs from config."""
        crons_config = self.config.get("crons", {})
        jobs_config = crons_config.get("jobs", [])

        for job_config in jobs_config:
            job = CronJob(
                name=job_config["name"],
                schedule=job_config["schedule"],
                skill=job_config["skill"],
                action=job_config["action"],
                params=job_config.get("params", {}),
            )
            self.jobs.append(job)
            logger.info(f"Loaded cron job: {job.name} ({job.schedule})")

    async def run(self):
        """Main scheduler loop."""
        logger.info("Starting Jarvis Scheduler...")
        await self.agent.initialize()
        self._load_jobs()
        logger.info(f"Loaded {len(self.jobs)} cron jobs")

        stop_event = asyncio.Event()

        def _handle_signal():
            stop_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_signal)

        while not stop_event.is_set():
            now = datetime.now()

            for job in self.jobs:
                if job.should_run(now):
                    logger.info(f"Running cron job: {job.name}")
                    job.last_run = now
                    try:
                        result = await self.agent.run_skill(job.skill, job.action, job.params)
                        logger.info(f"Job {job.name} completed: {str(result)[:200]}")
                    except Exception as e:
                        logger.error(f"Job {job.name} failed: {e}")

            # Sleep until next minute
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass

        logger.info("Scheduler stopped")
        await self.agent.shutdown()


def main():
    import os
    logging.basicConfig(
        level=getattr(logging, os.getenv("AGENT_LOG_LEVEL", "INFO")),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    scheduler = JarvisScheduler()
    asyncio.run(scheduler.run())


if __name__ == "__main__":
    main()
