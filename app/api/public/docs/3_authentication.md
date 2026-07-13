# Autenticação via API Key

Para autenticar suas requisições, inclua a sua chave de API no header `X-API-Key` de todas as chamadas.

## Headers Obrigatórios

<table>
  <tr>
    <th width="30%">Header</th>
    <th width="35%">Formato</th>
    <th width="35%">Exemplo</th>
  </tr>
  <tr>
    <td>`X-API-Key`</td>
    <td>Começa com `sk_live_`</td>
    <td>`sk_live_prod_abc123xyz`</td>
  </tr>
</table>

## Resposta do endpoint `/validate-api-key`

<table>
  <tr>
    <th width="30%">Campo</th>
    <th width="20%">Tipo</th>
    <th width="50%">Descrição</th>
  </tr>
  <tr>
    <td>`success`</td>
    <td>`boolean`</td>
    <td>`true` em caso de sucesso</td>
  </tr>
  <tr>
    <td>`data.type`</td>
    <td>`string`</td>
    <td>Tipo da empresa: `terminal` ou `trucking`</td>
  </tr>
  <tr>
    <td>`data.username`</td>
    <td>`string`</td>
    <td>Username da empresa no GateIn</td>
  </tr>
  <tr>
    <td>`data.name`</td>
    <td>`string`</td>
    <td>Razão social da empresa</td>
  </tr>
  <tr>
    <td>`data.tax_id`</td>
    <td>`string`</td>
    <td>CNPJ da empresa</td>
  </tr>
</table>

## Erros

<table>
  <tr>
    <th width="15%">HTTP</th>
    <th width="40%">`code`</th>
    <th width="45%">Causa</th>
  </tr>
  <tr>
    <td>`401`</td>
    <td>`INVALID_API_KEY_FORMAT`</td>
    <td>Chave sem prefixo `sk_live_` ou malformada</td>
  </tr>
</table>
