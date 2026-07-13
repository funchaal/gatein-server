# Getting Started

Bem-vindo à documentação oficial da **API de Integração Externa do GateIn**. 

Esta API foi desenvolvida para permitir que parceiros, transportadoras e terminais integrem seus sistemas de forma nativa com a plataforma GateIn. Através deste canal, você pode automatizar fluxos de agendamentos, viagens e validações cadastrais em tempo real.

---

## O que você pode fazer?

Esta API expõe endpoints projetados especificamente para cenários de integração de sistemas B2B:

1. **Gestão de Agendamentos (Appointments):** Ideal para **Terminais** controlarem janelas horárias, placas de veículos, dados cadastrais de motoristas e acompanharem logs detalhados de execução.
2. **Gestão de Viagens (Trips):** Ideal para **Transportadoras** e **Embarcadores** informarem a movimentação de frotas, definirem origens/destinos, associarem motoristas e realizarem rastreabilidade.
3. **Validação Cadastral e Autenticação:** Endpoints utilitários para checar credenciais de chaves de API e decodificar tokens JWT utilizados em dispositivos móveis.

---

## Estrutura de Retorno Padrão

Todas as respostas de sucesso da nossa API retornam um envelope JSON unificado com a seguinte assinatura:

```json
{
  "success": true,
  "data": { ... }
}
```

### Tratamento de Erros e Padrão de Falhas

Quando ocorre uma falha de validação, regra de negócio ou erro interno, o status HTTP correspondente é retornado (ex: `400`, `401`, `409`, etc) juntamente com um objeto descritivo no corpo da resposta:

```json
{
  "detail": {
    "code": "CODIGO_DO_ERRO",
    "message": "Descrição humanizada do problema para facilitar o debug.",
    "suggestion": "Sugestão prática de como corrigir ou contatar o suporte."
  }
}
```

## Principais Códigos de Erro

<table>
  <tr>
    <th width="40%">Código (`code`)</th>
    <th width="60%">Causa / Descrição</th>
  </tr>
  <tr>
    <td>`EMPTY_PAYLOAD`</td>
    <td>Enviou uma requisição com array/objeto vazio ou sem corpo de dados.</td>
  </tr>
  <tr>
    <td>`INVALID_API_KEY_FORMAT`</td>
    <td>A chave informada no header `X-API-Key` não começa com `sk_live_` ou está mal formatada.</td>
  </tr>
  <tr>
    <td>`INVALID_API_KEY`</td>
    <td>Credencial inexistente ou revogada.</td>
  </tr>
  <tr>
    <td>`DUPLICATE_KEY`</td>
    <td>Um ou mais registros já existem com as chaves externas (`ref`) informadas.</td>
  </tr>
  <tr>
    <td>`INVALID_LAYOUT_REF`</td>
    <td>A referência de layout informada não existe no terminal ou transportadora associada.</td>
  </tr>
  <tr>
    <td>`REFS_NOT_FOUND`</td>
    <td>Uma ou mais referências fornecidas para atualização ou deleção não foram encontradas no banco.</td>
  </tr>
</table>
