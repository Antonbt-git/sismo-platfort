# Modelo de datos — diagrama ER

Migracion inicial: `database/migrations/versions/0001_inicial.py` (UUID internos, UTC, CHECK de rangos).

```mermaid
erDiagram
    users ||--o{ user_roles : tiene
    roles ||--o{ user_roles : asigna
    users ||--o{ audit_logs : genera
    users ||--o{ datasets : crea
    users ||--o{ ml_experiments : "entrena"
    users ||--o{ alert_rules : crea
    users ||--o{ report_jobs : solicita

    data_sources ||--o{ seismic_events : reporta
    data_sources ||--o{ ingestion_runs : registra

    seismic_events ||--o{ alerts : origina
    alert_rules ||--o{ alerts : dispara
    alerts ||--o{ alert_deliveries : entrega

    datasets ||--o{ ml_experiments : alimenta
    ml_experiments ||--o{ model_registry : versiona
    model_registry ||--o{ risk_estimates : publica

    users {
        uuid id PK
        string full_name
        string email UK
        string password_hash
        string status
        json roles
        datetime created_at
        datetime last_login_at
    }
    roles {
        uuid id PK
        string name UK
    }
    data_sources {
        uuid id PK
        string name UK
        string organization
        string base_url
        string source_type
        string status
        bool enabled
        string license
        int frequency_minutes
        datetime last_sync_at
        datetime last_success_at
        int last_latency_ms
        string config_ref
    }
    ingestion_runs {
        uuid id PK
        uuid source_id FK
        datetime started_at
        datetime finished_at
        string status
        int records_seen
        int records_inserted
        int records_updated
        text error_summary
    }
    seismic_events {
        uuid id PK
        string external_id
        uuid source_id FK
        datetime occurred_at
        float latitude
        float longitude
        float magnitude
        string magnitude_type
        float depth_km
        string place
        string region
        string source_url
        datetime received_at
        string review_status
    }
    datasets {
        uuid id PK
        string name
        int version
        json query_spec
        int row_count
        json quality_report
        uuid created_by FK
    }
    ml_experiments {
        uuid id PK
        string name
        string task_type
        string algorithm
        uuid dataset_id FK
        json feature_spec
        string target_name
        json params
        json metrics
        json validation_spec
        int seed
        string status
        string artifact_uri
        text limitations
    }
    model_registry {
        uuid id PK
        uuid experiment_id FK
        int version
        string status
        uuid approved_by FK
        datetime approved_at
        text limitations
    }
    risk_estimates {
        uuid id PK
        uuid model_id FK
        string area_code
        datetime window_start
        datetime window_end
        string metric_name
        float value
        float lower_bound
        float upper_bound
        text disclaimer
        bool is_experimental
    }
    alert_rules {
        uuid id PK
        string name UK
        json condition_json
        string severity
        json zone_spec
        json channels
        int cooldown_seconds
        bool requires_approval
        bool enabled
        uuid created_by FK
        datetime last_triggered_at
    }
    alerts {
        uuid id PK
        uuid event_id FK
        uuid rule_id FK
        string severity
        string title
        text message
        string source_url
        string status
        string dedupe_key
        uuid approved_by FK
        datetime approved_at
    }
    alert_deliveries {
        uuid id PK
        uuid alert_id FK
        string channel
        string destination_ref
        string status
        int attempts
        datetime last_attempt_at
        datetime delivered_at
        string error_code
    }
    audit_logs {
        uuid id PK
        uuid actor_id FK
        string action
        string entity_type
        string entity_id
        json before_json
        json after_json
        datetime occurred_at
        string result
        string correlation_id
    }
    report_jobs {
        uuid id PK
        uuid requested_by FK
        string report_type
        json filters_json
        string status
        string file_ref
        datetime created_at
        datetime expires_at
    }
```

Reglas clave:
- `seismic_events`: unica `(external_id, source_id)` → ingesta idempotente sin duplicados.
- `alerts`: unica `(event_id, rule_id, dedupe_key)` → deduplicacion de avisos.
- `risk_estimates`: jamas se mezclan con eventos observados; toda fila identifica modelo/versions y lleva disclaimer.
- `audit_logs`: bitacora protegida; sin tokens ni secretos.
