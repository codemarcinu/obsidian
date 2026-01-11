import json
import ollama
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

from config import ProjectConfig

# Definicja struktury dla Bielika/Llamy (Structured Output emulation)
class LifeAdminItem(BaseModel):
    category: str = Field(description="Kategoria: 'Zakupy', 'Dom', 'Zdrowie', 'Finanse', 'Inne'")
    action_item: str = Field(description="Konkretne zadanie do wykonania")
    due_date: Optional[str] = Field(description="Data w formacie YYYY-MM-DD jeśli wykryto, inaczej null")
    context: str = Field(description="Oryginalny kontekst lub notatka")

def process_voice_note_for_life(text_content: str, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Zamienia strumień świadomości (transkrypcję) na ustrukturyzowaną notatkę domową.
    """
    # Use fast model by default for JSON tasks as it's often better tuned for it or just faster
    model = model_name or ProjectConfig.OLLAMA_MODEL_FAST 
    
    prompt = f"""
    Jesteś osobistym asystentem. Przeanalizuj poniższą notatkę głosową. 
    Wyciągnij z niej zadania (ToDo), zakupy i ważne informacje.
    Ignoruj przerywniki "yyy", "eee".
    
    TREŚĆ:
    {text_content}
    
    Zwróć odpowiedź w formacie JSON jako listę obiektów z polami:
    - category (String: 'Zakupy', 'Dom', 'Zdrowie', 'Finanse', 'Inne')
    - action_item (String: Konkretne zadanie)
    - due_date (String: YYYY-MM-DD lub null)
    - context (String: Oryginalne zdanie/kontekst)
    """
    
    try:
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            format='json'
        )
        content = response['message']['content']
        data = json.loads(content)
        
        # Ollama sometimes returns a dict with a key holding the list, or just the list.
        # Let's normalize.
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try to find a list in values
            for key, value in data.items():
                if isinstance(value, list):
                    return value
            # If no list found, maybe the dict itself is one item?
            if "action_item" in data:
                return [data]
            
        return [] # Fallback
            
    except Exception as e:
        print(f"Error in life admin processing: {e}")
        return []
