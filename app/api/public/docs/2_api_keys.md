# Chaves de API (API Keys)

As Chaves de API são segredos únicos gerados para cada empresa (seja um Terminal ou uma Transportadora) para permitir a autenticação de sistemas externos (B2B) nas APIs do GateIn.

---

## Como as Chaves de API Funcionam?

Qualquer requisição feita aos endpoints da API (ex: cadastrar agendamentos ou viagens) precisa incluir a chave de API no cabeçalho HTTP:

* **Header:** `X-API-Key`
* **Formato:** Inicia sempre com o prefixo `sk_live_` (exemplo: `sk_live_prod_abc123xyz_key`).
* **Segurança:** A chave de API dá acesso total de escrita/leitura para as operações da sua empresa. Trate-a como uma senha: nunca insira a chave em códigos que rodam no navegador do cliente (frontend) nem faça commit dela em repositórios públicos.

---

## Como Gerar ou Rotacionar uma Chave de API no Website?

Para obter a sua credencial ou rotacionar a chave existente, siga o passo a passo no painel do GateIn:

1. **Acesse o Sistema:** Faça login na plataforma web do GateIn com sua conta de administrador.
2. **Navegue até Configurações:** No menu lateral esquerdo, clique em **Configurações**.
3. **Selecione a aba Integrações:** Clique na aba ou seção de **Chaves de API** / **Integrações**.
4. **Gerar/Rotacionar Chave:** Clique no botão **Gerar Chave** ou **Rotacionar Chave**. *Nota: Cada empresa possui apenas uma única chave de API ativa por vez. Ao gerar uma nova chave, a anterior é automaticamente revogada e invalidada.*
5. **Copie o Segredo:** A chave será gerada e exibida na tela. **Atenção:** Por motivos de segurança, essa chave só é mostrada uma única vez. Salve-a em um gerenciador de segredos ou cofre seguro antes de fechar a janela.

---

## Validando sua Chave via API

Para testar a integração e garantir que sua chave está ativa e configurada corretamente, envie uma requisição para o endpoint `/validate-api-key`:

#### Exemplo em cURL:
```bash
curl -X GET "https://api.gatein.com/api/v1/validate-api-key" \
  -H "X-API-Key: sk_live_exemplo_suachavesecreta"
```

#### Exemplo em Python:
```python
import requests

url = "https://api.gatein.com/api/v1/validate-api-key"
headers = {
    "X-API-Key": "sk_live_exemplo_suachavesecreta"
}

response = requests.get(url, headers=headers)
print(response.json())
```

#### Exemplo em JavaScript (Node/Fetch):
```javascript
fetch('https://api.gatein.com/api/v1/validate-api-key', {
  method: 'GET',
  headers: {
    'X-API-Key': 'sk_live_exemplo_suachavesecreta'
  }
})
.then(res => res.json())
.then(data => console.log(data))
.catch(err => console.error(err));
```
