from typing import Dict, Set

class TypingManager:
    def __init__(self):
        # Stores active typing users per conversation: { conversation_id: set(user_ids) }
        self.active_typing: Dict[str, Set[str]] = {}

    def start_typing(self, conversation_id: str, user_id: str):
        conversation_id = str(conversation_id)
        user_id = str(user_id)
        if conversation_id not in self.active_typing:
            self.active_typing[conversation_id] = set()
        self.active_typing[conversation_id].add(user_id)

    def stop_typing(self, conversation_id: str, user_id: str):
        conversation_id = str(conversation_id)
        user_id = str(user_id)
        if conversation_id in self.active_typing:
            self.active_typing[conversation_id].discard(user_id)
            if not self.active_typing[conversation_id]:
                del self.active_typing[conversation_id]

    def get_typing_users(self, conversation_id: str) -> Set[str]:
        return self.active_typing.get(str(conversation_id), set())

typing_manager = TypingManager()