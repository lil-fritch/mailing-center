from typing import Optional
import asyncio

from pydantic import BaseModel, Field
from parallel import Parallel

from app.core.settings import settings
from app.core.logger import get_logger


class EnrichmentOutput(BaseModel):
    """
    Defines the expected output structure for the Parallel enrichment task.
    """
    summary: Optional[str] = Field(
        description="A detailed summary of the information found based on the enrichment prompt. "
                    "This field should be null if no relevant information is found."
    )
    key_points: Optional[list[str]] = Field(
        default=None,
        description="List of key findings or important points discovered during enrichment."
    )


class ParallelEnricher:
    """
    Enriches B2B object data through web research using Parallel AI.
    """
    def __init__(self):
        self.logger = get_logger(__name__)
        if not settings.parallel_key:
            self.logger.warning("PARALLEL_KEY is not configured in settings. Enrichment will be skipped.")
            self.client = None
        else:
            self.client = Parallel(api_key=settings.parallel_key)
            self.logger.info("ParallelEnricher initialized successfully.")

    async def enrich_object(self, website: str, prompt: str, object_name: str = "object") -> Optional[str]:
        """
        Enriches data about a B2B object through web research.
        This method runs asynchronously to avoid blocking the event loop.
        
        Args:
            website: URL of the website to analyze
            prompt: What to look for (from campaign.parsing_prompt)
            object_name: Name of the object for logging purposes
            
        Returns:
            Text summary of found information or None
        """
        if not self.client:
            self.logger.warning("ParallelEnricher: client not initialized, skipping enrichment")
            return None
            
        if not website or not website.strip():
            self.logger.warning("ParallelEnricher: no website provided for '%s', skipping enrichment", object_name)
            return None

        self.logger.info("ParallelEnricher: enriching data for '%s' at %s", object_name, website)

        input_data = {
            "url": website,
            "query": prompt
        }

        try:
            # Run the synchronous Parallel API call in a thread pool to avoid blocking the event loop
            def run_enrichment():
                return self.client.task_run.execute(
                    input=input_data,
                    output=EnrichmentOutput,
                    processor="base"
                )
            
            # Execute in thread pool without timeout (as requested)
            run_result = await asyncio.to_thread(run_enrichment)

            if run_result and run_result.output and run_result.output.parsed:
                parsed = run_result.output.parsed
                summary = parsed.summary or ""
                
                # Add key points if available
                if parsed.key_points and len(parsed.key_points) > 0:
                    key_points_text = "\n".join(f"- {point}" for point in parsed.key_points)
                    enriched_text = f"{summary}\n\nKey points:\n{key_points_text}"
                else:
                    enriched_text = summary
                
                if enriched_text.strip():
                    self.logger.info(
                        "ParallelEnricher: enrichment found for '%s': %s",
                        object_name,
                        enriched_text
                    )
                    return enriched_text
                else:
                    self.logger.info("ParallelEnricher: no relevant information found for '%s'", object_name)
                    return None
            
            self.logger.info("ParallelEnricher: no data returned for '%s'", object_name)
            return None
                
        except Exception as e:
            self.logger.error(
                "ParallelEnricher: error while enriching '%s' at %s: %s",
                object_name,
                website,
                str(e),
                exc_info=True
            )
            return None


parallel_enricher = ParallelEnricher()