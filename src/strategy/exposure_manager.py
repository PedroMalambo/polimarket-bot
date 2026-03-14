import re
from typing import List, Tuple, Dict, Any

# Palabras comunes en Polymarket que no aportan valor semántico para la comparación
STOPWORDS = {"will", "the", "a", "an", "before", "in", "of", "to", "for", "on", "by", "at", "is", "be", "this", "that", "what", "when", "who", "how", "and", "or", "win", "happen"}

def _normalize_and_tokenize(text: str) -> set:
    """Limpia el texto, lo pasa a minúsculas y extrae palabras clave útiles."""
    # Elimina signos de puntuación
    clean_text = re.sub(r'[^\w\s]', '', text).lower()
    tokens = set(clean_text.split())
    # Remueve stopwords
    return tokens - STOPWORDS

def calculate_overlap(text1: str, text2: str) -> float:
    """Calcula qué tanto se solapan dos textos basándose en sus palabras clave."""
    set1 = _normalize_and_tokenize(text1)
    set2 = _normalize_and_tokenize(text2)
    
    if not set1 or not set2:
        return 0.0
        
    intersection = set1.intersection(set2)
    # Usamos el overlap coefficient: (Intersección / Tamaño del set más pequeño)
    # Esto ayuda si un mercado dice "Rihanna" y otro "Will Rihanna release an album?"
    overlap = len(intersection) / min(len(set1), len(set2))
    return overlap

def filter_candidates_by_exposure(
    candidates: List[Dict[str, Any]], 
    open_questions: List[str], 
    threshold: float = 0.45
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Filtra candidatos que sean semánticamente muy similares a posiciones ya abiertas.
    Retorna: (candidatos_permitidos, detalles_de_exclusion)
    """
    allowed_candidates = []
    excluded_details = []

    for candidate in candidates:
        # Algunos endpoints de Polymarket devuelven 'market' en lugar de 'market_id', cubrimos ambos
        market_id = candidate.get("market", candidate.get("market_id", "unknown"))
        candidate_question = candidate.get("question", "")
        
        if not candidate_question:
            allowed_candidates.append(candidate)
            continue

        is_excluded = False
        for open_q in open_questions:
            similarity = calculate_overlap(candidate_question, open_q)
            if similarity >= threshold:
                excluded_details.append({
                    "market_id": market_id,
                    "question": candidate_question,
                    "reason": f"Overlap {similarity:.2f} con posición abierta: '{open_q}'"
                })
                is_excluded = True
                break # Si ya chocó con una posición, no hace falta revisar las demás
        
        if not is_excluded:
            allowed_candidates.append(candidate)

    return allowed_candidates, excluded_details
