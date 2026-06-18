
from urllib.parse import urlparse

def extract_domain(url: str) -> str:
    """
    Transforma 'https://www.sistema.com.br/agendar?id=1' 
    em 'sistema.com.br'
    """
    parsed_url = urlparse(str(url))
    domain = parsed_url.netloc # Retorna 'www.sistema.com.br'
    
    # Remove o 'www.' se existir, para padronizar
    if domain.startswith('www.'):
        domain = domain[4:]
        
    return domain