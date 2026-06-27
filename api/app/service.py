"""Generation service: generate a poem, persist it, enqueue asset jobs."""

from __future__ import annotations

from typing import Optional, Union

from sqlalchemy.orm import Session

from .characters import Character
from .claude_client import PoemGenerator
from .models import Poem
from .queue import JobQueue
from .repository import persist_poem


class GenerationService:
    def __init__(self, generator: PoemGenerator, queue: JobQueue):
        self.generator = generator
        self.queue = queue

    def generate(
        self,
        session: Session,
        character: Union[Character, str],
        theme: Optional[str] = None,
        lang: str = "en",
        generate_image: bool = True,
        generate_audio: bool = True,
    ) -> Poem:
        result = self.generator.generate(character, theme)
        poem, jobs = persist_poem(
            session,
            result,
            theme=theme,
            lang=lang,
            model=self.generator.config.model,
            generate_image=generate_image,
            generate_audio=generate_audio,
        )
        for job in jobs:
            self.queue.enqueue(job.type, job.id)
        return poem
