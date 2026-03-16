import re
from typing import List, Tuple, Dict, Any

# Stopwords optimizadas para Polymarket
STOPWORDS = {
    "will", "the", "a", "an", "before", "in", "of", "to", "for", "on", "by", "at", 
    "is", "be", "this", "that", "what", "when", "who", "how", "and", "or", "happen",
    "next", "than", "more", "less", "about", "any", "each", "was", "were"
}

def _normalize_and_tokenize(text: str) -> set:
    """Limpia el texto y extrae palabras clave con peso semántico."""
    # Elimina signos de puntuación pero mantiene números (importantes para fechas/años)
    clean_text = re.sub(r'[^\w\s]', '', text).lower()
    
    # Stemming ultra-ligero manual para Polymarket
    # Convierte 'winning' -> 'win', 'wins' -> 'win', 'elections' -> 'elect'
    tokens = []
    for word in clean_text.split():
        if word in STOPWORDS:
            continue
        word = re.sub(r'ing$|s$|ed$', '', word) # Quita sufijos comunes
        if len(word) > 1: # Ignora letras sueltas
            tokens.append(word)
            
    return set(tokens)

def calculate_overlap(text1: str, text2: str) -> float:
    """Calcula el solapamiento semántico con enfoque en entidades clave."""
    set1 = _normalize_and_tokenize(text1)
    set2 = _normalize_and_tokenize(text2)
    
    if not set1 or not set2:
        return 0.0
        
    intersection = set1.intersection(set2)
    
    # Coeficiente de Overlap (Szymkiewicz–Simpson)
    # Es excelente para detectar si un tema está 'contenido' en otro
    overlap = len(intersection) / min(len(set1), len(set2))
    
    # PENALIZACIÓN EXTRA: Si comparten 3 o más palabras (ej. "Trump", "Elon", "Starship")
    # la probabilidad de que sean el mismo trade es altísima
    if len(intersection) >= 3:
        overlap = max(overlap, 0.80) 
        
    return overlap

def filter_candidates_by_exposure(
    candidates: List[Dict[str, Any]], 
    open_questions: List[str], 
    threshold: float = 0.45
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Filtra candidatos para evitar sobre-exposición a temas específicos.
    """
    allowed_candidates = []
    excluded_details = []

    for candidate in candidates:
        m_id = candidate.get("id", candidate.get("market_id", "unknown"))
        candidate_question = candidate.get("question", "")
        
        if not candidate_question:
            allowed_candidates.append(candidate)
            continue

        is_excluded = False
        for open_q in open_questions:
            similarity = calculate_overlap(candidate_question, open_q)
            
            if similarity >= threshold:
                excluded_details.append({
                    "market_id": str(m_id),
                    "question": candidate_question,
                    "reason": f"Overlap {similarity:.2f} con '{open_q[:40]}...'"
                })
                is_excluded = True
                break
        
        if not is_excluded:
            allowed_candidates.append(candidate)

    return allowed_candidates, excluded_details
