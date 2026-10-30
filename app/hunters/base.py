from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger("omnilead.hunter")

class BaseLeadHunter(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def hunt(self) -> List[Dict[str, Any]]:
        """
        Execute search and return list of discovered raw lead dictionaries.
        Each dictionary should contain:
        - title: str
        - source: str
        - original_url: str
        - raw_content: str
        - contact_name: Optional[str]
        - contact_email: Optional[str]
        - contact_phone: Optional[str]
        - business_name: Optional[str]
        - niche: Optional[str]
        - website_url: Optional[str]
        - has_website: bool
        """
        pass
