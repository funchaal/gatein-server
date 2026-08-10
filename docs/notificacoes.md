# 🔔 Especificação do Sistema de Notificações Push (GateIn)

Este documento descreve detalhadamente **todas as notificações push possíveis no ecossistema GateIn**, suas regras de disparo, motivos/objetivos de negócio, payloads de dados e a arquitetura de deduplicação para garantir que notificações agendadas sejam entregues **uma única vez**.

---

## 1. Visão Geral

As notificações no GateIn são processadas via **Firebase Cloud Messaging (FCM)** e enviadas aos dispositivos móveis dos motoristas com base no seu **CPF (tax_id)**. 

No backend (`gatein-server`), as notificações são disparadas em dois cenários principais:
1. **Eventos em Tempo Real (Event-Driven)**: Ações tomadas via API pública de integração, rotas do aplicativo ou handshakes Socket.IO com totens físicos de terminais.
2. **Jobs Automatizados (Cron / Scheduler)**: Tarefas executadas periodicamente pelo `APScheduler` para checar horários de agendamento, janelas de tolerância e inatividade.

---

## 2. Tabela Resumo de Notificações

| Código / `type` | Título Exibido | Disparo / Origem | Frequência / Regra | Público-Alvo | Motivo / Objetivo de Negócio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `REMINDER_1DAY` | Lembrete de Agendamento | Job `check_1day_reminders` (1h) | 23h a 25h antes do `window_start` | Motorista (`user_tax_id`) | Alertar com 24h de antecedência para planejamento de viagem. |
| `COUNTDOWN` | Agendamento Próximo | Job `check_12h_reminders` (15min) | ~12h antes do `window_start` | Motorista (`user_tax_id`) | Notificar 12h antes e fornecer dados de contagem regressiva. |
| `WINDOW_OPEN` | Janela de Check-in Aberta | Job `check_window_open` (5min) | Momento em que abre a janela de check-in | Motorista (`user_tax_id`) | Avisar que o acesso ao pátio/terminal está liberado para check-in. |
| `ON_GOING` | Operação em Andamento | Job `check_in_progress` (5min) | Quando o agendamento muda para `ON_GOING` | Motorista (`user_tax_id`) | Orientar o motorista a seguir as instruções do terminal em operação. |
| `CANCELLED` | Agendamento Desativado | Job `deactivate_abandoned_appointments` (5min) | > 2h sem ping ou estouro de tolerância | Motorista (`user_tax_id`) | Avisar que o agendamento foi encerrado/desativado por inatividade. |
| `SCHEDULED_CREATED` | Novo Agendamento | API pública (`POST /appointments`) | Imediato após criação do agendamento | Motorista (`user_tax_id`) | Informar a criação de um novo agendamento pela transportadora/terminal. |
| `SCHEDULED_UPDATE` | Horário Alterado / Dados Atualizados | API pública (`PUT /appointments`) | Imediato após alteração de dados/horário | Motorista (`user_tax_id`) | Notificar sobre remarcação de horários ou alteração de dados operacionais. |
| `CANCELLED` | Agendamento Cancelado | API pública (`DELETE /appointments`) | Imediato após cancelamento do agendamento | Motorista (`user_tax_id`) | Alertar sobre o cancelamento do agendamento para evitar deslocamentos. |
| `CHECKED-IN` | Check-in Realizado | Handshake Socket (`POST /checkin/{id}`) | Imediato após confirmação no totem | Motorista (`user_tax_id`) | Confirmar a recepção da senha/ticket de entrada no terminal. |
| `CHECKIN_FAILED` | Tempo Limite Excedido / Falha no Check-in | Handshake Socket (`POST /checkin/{id}`) | Falha ou timeout (> 15s) de comunicação | Motorista (`user_tax_id`) | Informar erro de comunicação com totem para que o motorista retente. |
| `CHECKIN_CANCELLED` | Check-in Cancelado | Endpoint (`POST /checkin/cancel/{id}`) | Imediato após o cancelamento do check-in | Motorista (`user_tax_id`) | Confirmar a reversão do status do agendamento de volta para Agendado. |
| `TEST` | Notificação de Teste | Endpoint (`POST /notifications/test`) | Manual / Teste sob demanda | Usuário Autenticado | Validar recebimento de push e registro de tokens FCM no aparelho. |
| `ANNOUNCEMENT` | *Título do Anúncio* | Painel Web (`POST /announcements`) | Publicação de anúncio institucional | Motoristas da empresa | Comunicar avisos gerais, alertas de segurança ou recados do terminal. |

---

## 3. Detalhamento por Notificação

### 3.1. Notificações de Jobs Automatizados (Scheduler)

#### 1. Lembrete de 1 Dia (`REMINDER_1DAY`)
- **Regra**: Filtra agendamentos `ACTIVE` cuja janela inicial (`window_start`) ocorrerá entre 23 e 25 horas no futuro.
- **Deduplicação**: O job verifica na tabela `appointments_logs` se já existe registro com `event = 'notification_sent'` e `push_type = 'REMINDER_1DAY'`. Se existir, pula o envio.
- **Payload Data**: `{"type": "REMINDER_1DAY", "count": "1"}`

#### 2. Lembrete de 12 Horas (`COUNTDOWN`)
- **Regra**: Filtra agendamentos `ACTIVE` que iniciarão em aproximadamente 12 horas (janela de ±7.5 minutos).
- **Deduplicação**: Verifica se `push_type = 'COUNTDOWN'` já foi registrado para o agendamento.
- **Payload Data**: `{"type": "COUNTDOWN", "appointment_id": "<uuid>", "target_timestamp": "<iso_date>", "count": "1"}`
- **Comportamento no App**: O aplicativo intercepta o tipo `COUNTDOWN` e pode exibir um timer/contagem regressiva local.

#### 3. Janela Aberta (`WINDOW_OPEN`)
- **Regra**: Filtra agendamentos `ACTIVE` em que o horário atual está dentro da janela de check-in (`window_start - start_tolerance` até `window_end + end_tolerance`).
- **Deduplicação**: **Disparado estritamente 1 única vez por agendamento**. O scheduler consulta `appointments_logs` e, caso já tenha enviado a notificação de janela aberta para aquele agendamento, ignora nas execuções subsequentes de 5 em 5 minutos.
- **Payload Data**: `{"type": "WINDOW_OPEN", "appointment_id": "<uuid>", "window_close": "<iso_date>"}`

#### 4. Operação em Andamento (`ON_GOING`)
- **Regra**: Filtra agendamentos que entraram no status `ON_GOING`.
- **Deduplicação**: Disparado 1 única vez assim que a operação transiciona para em andamento.
- **Payload Data**: `{"type": "ON_GOING", "appointment_id": "<uuid>"}`

#### 5. Agendamento Desativado por Inatividade (`CANCELLED` / `DEACTIVATED`)
- **Regra**: Disparado quando um agendamento é desativado automaticamente por ultrapassar a tolerância de 2 horas sem check-in ou sem ping do terminal.
- **Payload Data**: `{"type": "CANCELLED", "appointment_id": "<uuid>"}`

---

### 3.2. Notificações de Integração e API Pública

#### 6. Novo Agendamento Criado (`SCHEDULED_CREATED`)
- **Regra**: Disparado via `POST /api/public/appointments` quando um novo agendamento é criado com o CPF do motorista.
- **Payload Data**: `{"type": "SCHEDULED_CREATED", "ref": "<ref_externa>"}`

#### 7. Alteração de Agendamento (`SCHEDULED_UPDATE`)
- **Regra**: Disparado via `PUT /api/public/appointments`. Envia mensagem de horário alterado caso os campos de data/tolerância mudem, ou de dados atualizados para outros atributos.
- **Payload Data**: `{"type": "SCHEDULED_UPDATE", "ref": "<ref_externa>", "change": "time" | "display"}`

#### 8. Cancelamento de Agendamento (`CANCELLED`)
- **Regra**: Disparado via `DELETE /api/public/appointments` quando a empresa cancela o agendamento.
- **Payload Data**: `{"type": "CANCELLED", "ref": "<ref_externa>"}`

---

### 3.3. Notificações de Check-in e Hardware Terminal

#### 9. Check-in Realizado (`CHECKED-IN`)
- **Regra**: Disparado após confirmação do totem físico e geração dos tickets de acesso.
- **Payload Data**: `{"type": "CHECKED-IN"}`

#### 10. Falha no Check-in (`CHECKIN_FAILED`)
- **Regra**: Disparado caso ocorra timeout (> 15s) ou falha no Socket de comunicação com o terminal físico.
- **Payload Data**: `{"type": "CHECKIN_FAILED"}`

#### 11. Check-in Cancelado (`CHECKIN_CANCELLED`)
- **Regra**: Disparado quando o check-in é desfeito via `POST /api/mobile/checkin/cancel/{appointment_id}`.
- **Payload Data**: `{"type": "CHECKIN_CANCELLED", "appointment_id": "<uuid>", "reason": "<motivo>"}`

---

### 3.4. Notificações Utilitárias e Institucionais

#### 12. Notificação de Teste (`TEST`)
- **Regra**: Disparado manualmente via `POST /api/mobile/notifications/test`.
- **Payload Data**: `{"type": "TEST"}`

#### 13. Anúncios da Empresa / Terminal (`ANNOUNCEMENT`)
- **Regra**: Disparado na publicação de novos anúncios para motoristas associados ao terminal.
- **Payload Data**: `{"type": "ANNOUNCEMENT", "announcement_id": "<uuid>"}`

---

## 4. Regra de Deduplicação e Envio Único

Para sanar a ocorrência de notificações repetidas durante a janela de agendamento (onde o job roda a cada 5 minutos), foi implementado o mecanismo de **Deduplicação por Log**:

Cada job automatizado armazena a chave `push_type` correspondente no campo `json` do log de agendamento (`AppointmentLog`). Antes de disparar qualquer push, o sistema realiza a verificação e impede reenvios desnecessários.
