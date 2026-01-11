import datetime
import ollama
import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import ProjectConfig

def run_weekly_review():
    today = datetime.date.today()
    # Calculate last 7 days
    dates = [today - datetime.timedelta(days=i) for i in range(7)]
    dates.reverse() # Chronological order
    
    daily_dir = ProjectConfig.OBSIDIAN_VAULT / "Daily"
    notes_content = ""
    found_count = 0
    
    print(f"Collecting notes from {dates[0]} to {dates[-1]}...")
    
    for date in dates:
        filename = f"{date.strftime('%Y-%m-%d')}.md"
        path = daily_dir / filename
        
        if path.exists():
            content = path.read_text(encoding='utf-8')
            notes_content += f"\n\n--- Dzień: {date} ---\n{content}"
            found_count += 1
        else:
            print(f"Missing: {filename}")
    
    if not notes_content:
        print("No daily notes found for this week.")
        return

    print(f"Found {found_count} notes. Analyzing with LLM ({ProjectConfig.OLLAMA_MODEL})...")
    
    prompt = f"""
    Jesteś moim osobistym trenerem i analitykiem (Reflection Agent). 
    Przeanalizuj moje notatki z ostatniego tygodnia (poniżej).
    
    Twoim zadaniem jest stworzenie "Tygodniowego Podsumowania" (Weekly Review).
    
    Odpowiedz w formacie Markdown na pytania:
    1. **Główne Tematy:** Co dominowało w moich myślach? Nad czym pracowałem?
    2. **Sukcesy:** Co udało się dowieźć? Jakie projekty ruszyły?
    3. **Wyzwania:** Czy widać oznaki stresu, blokady, prokrastynacji?
    4. **Sugestie:** Co warto zmienić w przyszłym tygodniu? Na czym się skupić? 
    
    Bądź szczery, bezpośredni i konstruktywny.
    
    NOTATKI Z OSTATNIEGO TYGODNIA:
    {notes_content[:25000]} 
    """
    
    try:
        response = ollama.chat(
            model=ProjectConfig.OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        review_content = response['message']['content']
        
        # Save Review
        review_dir = ProjectConfig.OBSIDIAN_VAULT / "Reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        week_num = today.strftime("%V")
        year = today.strftime("%Y")
        filename = f"Weekly_Review_{year}_W{week_num}.md"
        
        final_content = f"""
--- 
date: {today}
type: review
tags:
  - review
  - weekly
---

# 📅 Tygodniowy Przegląd: {year} Tydzień {week_num}

{review_content}

---
*Wygenerowano automatycznie przez System (Reflection Agent).*
"""
        
        output_path = review_dir / filename
        output_path.write_text(final_content, encoding='utf-8')
        print(f"Review saved to: {output_path}")
        
    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    run_weekly_review()
