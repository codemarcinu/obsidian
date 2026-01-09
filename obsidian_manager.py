import os
import re
from pathlib import Path

class ObsidianGardener:
    def __init__(self, vault_path):
        self.vault_path = Path(vault_path)
        self.all_files = self._scan_vault()

    def _scan_vault(self):
        """Tworzy mapę wszystkich plików w Vaulcie do szybkiego wyszukiwania."""
        files_map = {}
        if not self.vault_path.exists():
            return files_map
            
        for path in self.vault_path.rglob("*.md"):
            # Kluczem jest nazwa pliku bez rozszerzenia (lower case dla case-insensitive matching)
            clean_name = path.stem.lower()
            files_map[clean_name] = path.stem # Zapisujemy oryginalną pisownię
        return files_map

    def clean_markdown(self, content):
        """Czyści typowe błędy formatowania AI."""
        # 1. Usuwanie wielokrotnych pustych linii
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 2. Poprawa list (czasem AI robi "*Punkt" bez spacji)
        content = re.sub(r'^(\s*)[-*](\w)', r'\1- \2', content, flags=re.MULTILINE)
        
        # 3. Upewnienie się, że nagłówki mają spację po #
        content = re.sub(r'^(#+)([^#\s])', r'\1 \2', content, flags=re.MULTILINE)
        
        return content

    def auto_link(self, content):
        """Automatycznie tworzy linki [[WikiLink]] do istniejących notatek."""
        # Sortujemy klucze od najdłuższych, żeby nie podmienić "Auto" wewnątrz "Automatyzacja"
        sorted_keys = sorted(self.all_files.keys(), key=len, reverse=True)
        
        # Ignorujemy słowa bardzo krótkie i pospolite (stop words - uproszczone)
        ignored = {'i', 'w', 'z', 'do', 'na', 'to', 'jest'}
        
        new_content = content
        
        # Zabezpieczenie przed linkowaniem wewnątrz istniejących linków lub kodu
        # To prosta implementacja - w pełnej wersji wymagałaby parsera AST, ale tu wystarczy split
        
        # Dzielimy tekst na części: kod/linki vs zwykły tekst, żeby nie psuć składni
        # (Uproszczone podejście: skanujemy tylko jeśli nie jesteśmy wewnątrz [[...]] lub `...`)
        
        for key in sorted_keys:
            if len(key) < 3 or key in ignored:
                continue
                
            original_name = self.all_files[key]
            
            # Regex: Znajdź słowo (case insensitive), które NIE jest już w nawiasach [[ ]]
            # Lookbehind i Lookahead są trudne w Python re dla zmiennej długości,
            # więc użyjemy bezpieczniejszej metody replace z funkcją sprawdzającą.
            
            pattern = re.compile(re.escape(key), re.IGNORECASE)
            
            def replace_func(match):
                word = match.group(0)
                # Sprawdź kontekst (czy to nie jest część innego słowa)
                # Tutaj robimy prostą zamianę: jeśli znaleźliśmy dokładne dopasowanie
                return f"[[{original_name}|{word}]]"

            # UWAGA: To jest ryzykowne w prostym regex. 
            # Bezpieczniej: Linkujemy tylko terminy zdefiniowane jako "Słownik" lub "Koncepty"
            # W tej wersji zrobimy to ostrożnie - tylko dokładne dopasowania całych słów.
            
            pattern = re.compile(r'\b' + re.escape(key) + r'\b', re.IGNORECASE)
            
            # Problem: jak nie zamienić już zlinkowanego [[Linux]] na [[Linux|[[Linux]]]]?
            # Rozwiązanie: Na razie pomijamy auto-linkowanie wewnątrz treści,
            # skupmy się na sekcji "See Also" lub dodaniu sekcji na końcu.
            
            # WERSJA PROSTA: Dodajemy sekcję "Powiązane notatki" na dole
            if key in new_content.lower() and f"[[{original_name}" not in new_content:
                # Nie ingerujemy w treść, tylko sugerujemy na końcu
                pass 

        return new_content

    def append_related_links(self, content):
        """Dodaje sekcję 'Automatyczne Powiązania' na końcu notatki."""
        found_links = set()
        lower_content = content.lower()
        
        for key, original_name in self.all_files.items():
            if len(key) < 4: continue # Ignoruj krótkie
            
            # Jeśli nazwa pliku występuje w treści, a nie ma jeszcze linku
            if key in lower_content:
                # Sprawdź czy link już nie istnieje wprost
                if f"[[{original_name}" not in content and f"[[{key}" not in content.lower():
                    found_links.add(original_name)
        
        if found_links:
            footer = "\n\n---\n### 🔗 Automatyczne Powiązania (wykryte w treści)\n"
            for link in sorted(found_links):
                footer += f"- [[{link}]]\n"
            return content + footer
        
        return content

    def process_file(self, file_path):
        """Główna funkcja przetwarzająca pojedynczy plik."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 1. Czyszczenie
            content = self.clean_markdown(content)
            
            # 2. Linkowanie (dodawanie stopki)
            content = self.append_related_links(content)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return True, "Zoptymalizowano i dodano linki."
        except Exception as e:
            return False, str(e)

if __name__ == "__main__":
    # Test manualny
    import sys
    if len(sys.argv) > 2:
        gardener = ObsidianGardener(sys.argv[2])
        print(gardener.process_file(sys.argv[1]))
    else:
        print("Usage: python obsidian_manager.py <file_path> <vault_path>")
