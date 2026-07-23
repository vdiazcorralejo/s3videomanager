# 🚀 Plan de Evolución: S3 Video Manager → CDN de Video de Nivel Productivo

## Versión 1.0 – Octubre 2023

---

## 1. Diagnóstico de la Arquitectura Actual

| Componente | Estado Actual | Limitación Identificada |
|---|---|---|
| **Origen** | S3 estándar | Sin optimización CDN, latencia global alta |
| **Procesamiento** | Lambda con ffmpeg (deducido) | Timeout 15 min, sin cola de trabajos, sin escalado para HD masivo |
| **Formato** | M3U playlist (HLS básico) | Sin DASH, sin rendición adaptativa múltiple, sin DRM |
| **Entrega** | API Gateway + Pre-signed URLs | Sin edge caching, sin Origin Shield, sin soporte HTTP/2 |
| **Seguridad** | Authorizer personalizado básico | Sin WAF, sin Signed URLs/Cookies de CloudFront |
| **Autenticación** | Token custom | Sin integración Cognito/IAM, sin federación |

---

## 2. Fase 1: Infraestructura CDN Base con CloudFront

### 2.1 CloudFront Distribution como Front Edge

Reemplazar la entrega directa desde S3 por **CloudFront** como capa CDN global.

**Arquitectura objetivo:**

```
┌────────┐    ┌────────────┐    ┌────────┐    ┌──────────┐
│ Cliente │───▶│ CloudFront │───▶│ S3      │───▶│    CDK   │
│         │    │   CDN      │    │ Origin  │    │  Deploy  │
└────────┘    └────────────┘    └────────┘    └──────────┘
```

**Configuraciones clave (CDK L2 Construct `Distribution`):**

- **PriceClass** → `PriceClass.PRICE_CLASS_100` (solo regiones principales) o `PriceClass.PRICE_CLASS_ALL` según audiencia global.
- **DefaultBehavior** con `S3BucketOrigin` y **Origin Shield** habilitado.
- **Cache Policies** customizadas para segmentos HLS (`.ts`, `.m3u8`) con TTL largo (1 año para segmentos).
- **Viewer Protocol Policy** → `HTTPS_ONLY`.
- **AllowedMethods** → `GET, HEAD, OPTIONS`.
- **Lambda@Edge** (opcional) para reescritura de paths o autenticación básica en edge.

### 2.2 S3 Origin Access Control (OAC)

Reemplazar bucket público + pre-signed URLs con **OAC (Origin Access Control)** para que **solo CloudFront** pueda acceder al bucket.

```python video_content_delivery/video_content_delivery_stack.py (fragmento)
# Ejemplo CDK en tu stack principal
bucket = s3.Bucket(self, "VideoBucket",
    versioned=True,
    encryption=s3.BucketEncryption.S3_MANAGED,
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL
)

origin = origins.S3BucketOrigin(bucket,
    origin_access_control=origins.S3OriginAccessControl(
        signing_protocol=origins.SigningProtocol.SIGV4,
        signing_behavior=origins.SigningBehavior.ALWAYS
    )
)

distribution = cloudfront.Distribution(self, "VideoCDN",
    default_behavior=cloudfront.BehaviorOptions(
        origin=origin,
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
        cache_policy=cache_policy,
        origin_request_policy=origin_request_policy
    )
)
```

### 2.3 Custom Domain + ACM + Route53

- **ACM Certificate** en `us-east-1` para CloudFront (obligatorio).
- **Route53 Alias Record** apuntando al CloudFront Distribution.
- Dominio personalizado: `cdn.tu-app.com`.

---

## 3. Fase 2: Transcodificación Profesional con MediaConvert

Lambda tiene límite de 15 minutos y 10 GB de memoria. Para transcodificar videos 4K/HDR con múltiples rendiciones se necesita **AWS Elemental MediaConvert**.

### Nueva arquitectura de procesamiento

```
S3 Upload (.mp4)
     │
     ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  S3 Event   │───▶│   Step       │───▶│ MediaConvert │
│  (Object    │    │  Functions   │    │   Job        │
│   Created)  │    │  (Orchestra) │    │              │
└─────────────┘    └──────────────┘    └──────┬───────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │  S3 Output   │
                                       │  /hls/       │
                                       │  /dash/      │
                                       │  /thumbnails/│
                                       └──────────────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │  DynamoDB    │
                                       │  Update meta │
                                       └──────────────┘
```

### Implementación CDK con MediaConvert

```python video_content_delivery/video_content_delivery_stack.py (fragmento)
# Job Template para ABR (Adaptive Bitrate) – ejemplo simplificado
mediaconvert_job_template = {
    "Name": "VideoABR",
    "Settings": {
        "OutputGroups": [
            {
                "Name": "HLS",
                "OutputGroupSettings": {
                    "Type": "HLS_GROUP_SETTINGS",
                    "HlsGroupSettings": {
                        "SegmentLength": 6,
                        "MinSegmentLength": 0,
                        "Destination": f"s3://{bucket.bucket_name}/hls/"
                    }
                },
                "Outputs": [
                    {
                        "NameModifier": "_1080p",
                        "VideoDescription": {
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "MaxBitrate": 5000000,
                                    "RateControlMode": "QVBR"
                                }
                            },
                            "Height": 1080
                        }
                    },
                    {
                        "NameModifier": "_720p",
                        "VideoDescription": {
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "MaxBitrate": 2500000,
                                    "RateControlMode": "QVBR"
                                }
                            },
                            "Height": 720
                        }
                    }
                ]
            }
        ]
    }
}
```

### Step Functions para Orquestación

Reemplazar la Lambda única por **Step Functions** que:
1. Recibe el evento S3.
2. Inicia el Job de MediaConvert.
3. Espera callback (usando `task token`).
4. CloudWatch Event detecta completado del job.
5. Actualiza DynamoDB con URLs de los manifiestos.
6. Envía notificación SNS si falla.

---

## 4. Fase 3: Seguridad de Nivel CDN Enterprise

### 4.1 AWS WAF + CloudFront

```python video_content_delivery/video_content_delivery_stack.py (fragmento)
waf = wafv2.CfnWebACL(self, "VideoWAF",
    default_action=wafv2.CfnWebACL.AllowAction(),
    scope="CLOUDFRONT",
    rules=[
        wafv2.CfnWebACL.RuleProperty(
            name="RateLimit",
            priority=0,
            action=wafv2.CfnWebACL.BlockAction(),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    limit=1000,
                    aggregate_key_type="IP"
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="RateLimit",
                sampled_requests_enabled=True
            )
        ),
        wafv2.CfnWebACL.RuleProperty(
            name="AWS-AWSManagedRulesCommonRuleSet",
            priority=1,
            override_action=wafv2.CfnWebACL.OverrideAction(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS",
                    name="AWSManagedRulesCommonRuleSet"
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(...)
        )
    ]
)

distribution.add_web_acl(waf.attr_arn)
```

### 4.2 CloudFront Signed URLs / Signed Cookies

Reemplazar el autorizador de API Gateway + pre-signed URLs por **CloudFront Signed Cookies** (más escalables para listas de reproducción).

- Usar **CloudFront key pair** (generado desde el account).
- Una Lambda (o Step Function) valida al usuario (Cognito, JWT, etc.) y devuelve cookies firmadas.
- El cliente usa esas cookies para acceder directamente a CloudFront.

### 4.3 Cognito User Pools + Federated Identities

Para autenticación de usuarios finales (suscriptores de video):

```python video_content_delivery/video_content_delivery_stack.py (fragmento)
user_pool = cognito.UserPool(self, "VideoUserPool",
    self_sign_up_enabled=True,
    sign_in_aliases=cognito.SignInAliases(email=True),
    password_policy=cognito.PasswordPolicy(min_length=12)
)

user_pool_client = cognito.UserPoolClient(self, "Client",
    user_pool=user_pool,
    generate_secret=True,
    o_auth=cognito.OAuthSettings(
        flows=cognito.OAuthFlows(authorization_code_grant=True),
        callback_urls=["https://app.tu-app.com/callback"]
    )
)

identity_pool = cognito.CfnIdentityPool(self, "VideoIdentityPool",
    allow_unauthenticated_identities=False,
    cognito_identity_providers=[
        cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
            client_id=user_pool_client.user_pool_client_id,
            provider_name=user_pool.user_pool_provider_name
        )
    ]
)
```

---

## 5. Fase 4: Rendimiento Global y Escalabilidad

### 5.1 Global Accelerator + Multi-Region Origin (Opcional, según necesidad)

Para baja latencia global (streaming en vivo o casi-real) se puede integrar **AWS Global Accelerator** frente a CloudFront o como alternativa.

### 5.2 AWS Elemental MediaPackage

Para **empaquetado just-in-time** (HLS + DASH + CMAF desde un solo origen):

```
S3 (archivos sin procesar)
     │
     ▼
MediaConvert (transcodifica)
     │
     ▼
MediaPackage (empaqueta en vivo/bajo demanda)
     ├── HLS (.m3u8)
     ├── DASH (.mpd)
     └── CMAF (.mp4 fragmentado)
          │
          ▼
       CloudFront CDN
```

MediaPackage ofrece:
- **Endpoint packaging** automático a múltiples formatos.
- **Content encryption** con DRM (Widevine, FairPlay, PlayReady).
- **Time-shifted viewing** (pausa/retroceso en vivo).
- **Latencia configurable** (hasta 2 segundos para deportes en vivo).

### 5.3 S3 Intelligent-Tiering + Cross-Region Replication

```python video_content_delivery/video_content_delivery_stack.py (fragmento)
bucket = s3.Bucket(self, "VideoBucket",
    intelligent_tiering_configurations=[
        s3.IntelligentTieringConfiguration(
            name="VideoTiering",
            archive_access_tier_time=timedelta(days=90),
            deep_archive_access_tier_time=timedelta(days=180)
        )
    ],
    replication_destinations=[
        s3.ReplicationDestination(
            bucket=backup_bucket,
            storage_class=s3.StorageClass.STANDARD_SA_INFREQ_ACCESS
        )
    ]
)
```

---

## 6. Fase 5: Observabilidad y Monitoreo Enterprise

### 6.1 CloudWatch Dashboard + Alarms

```python video_content_delivery/video_content_delivery_stack.py (fragmento)
dashboard = cloudwatch.Dashboard(self, "VideoCDNDashboard")

dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title="CDN Requests & Errors",
        left=[
            distribution.metric_requests(statistic="Sum"),
            distribution.metric_total_error_rate(statistic="Average")
        ],
        right=[
            distribution.metric_4xx_error_rate(statistic="Average"),
            distribution.metric_5xx_error_rate(statistic="Average")
        ]
    ),
    cloudwatch.GraphWidget(
        title="CDN Data Transfer (GB)",
        left=[
            distribution.metric_download_bytes(statistic="Sum", label="Download"),
            distribution.metric_upload_bytes(statistic="Sum", label="Upload")
        ]
    ),
    cloudwatch.GraphWidget(
        title="MediaConvert Jobs",
        left=[
            mediaconvert_job.metric("CompletedJobs"),
            mediaconvert_job.metric("ErrorJobs")
        ]
    )
)

# Alarmas críticas
distribution.metric_5xx_error_rate().create_alarm(
    self, "CDN5xxAlarm",
    threshold=1,  # >1% de errores 5xx
    evaluation_periods=2,
    datapoints_to_alarm=2,
    alarm_description="High 5xx error rate in video CDN"
)
```

### 6.2 CloudTrail + Server Access Logs

- **CloudTrail** habilitado para todas las APIs de gestión.
- **S3 Server Access Logs** para logs de acceso detallados.
- **Athena + QuickSight** para análisis de logs CDN (geolocalización, videos más populares).

### 6.3 AWS X-Ray para trazas distribuidas

```python video_content_delivery/video_content_delivery_stack.py (fragmento)
# En las funciones Lambda y Step Functions
tracing = aws_lambda.Tracing.ACTIVE
```

---

## 7. Fase 6: CI/CD y Automatización

### 7.1 Pipeline CDK con etapas de aprobación

```yaml
# cdk-pipeline.yml
Pipeline:
  - Source: GitHub / CodeCommit
  - Synth: cdk synth
  - SelfMutation: true
  Stages:
    Dev:
      - DeployStack
      - TestStack (unit + integration tests)
    Staging:
      - DeployStack
      - TestStack (canary deployment)
      - ManualApproval
    Prod:
      - DeployStack (incluyendo CloudFront distribution)
      - SmokeTest
```

### 7.2 Uso de Contextos (Feature Flags)

```json
// cdk.json
{
  "context": {
    "enable-drm": true,
    "enable-mediapackage": true,
    "enable-global-accelerator": false,
    "cdn-price-class": "PriceClass_100"
  }
}
```

---

## 8. Fase 7: Optimización de Costos

| Componente | Estrategia de Ahorro |
|---|---|
| **MediaConvert** | Usar QVBR (calidad variable) sobre CBR (ahorra 30-50%) |
| **CloudFront** | PriceClass_100 si tráfico solo USA/Europa |
| **S3** | Intelligent‑Tiering + Lifecycle Policies |
| **Lambda** | Provisioned Concurrency solo para picos predecibles |
| **API Gateway** | Migrar a HTTP API (más barato que REST API) |

---

## 9. Roadmap de Implementación

| Sprint | Entregables | Constructo CDK a Crear |
|---|---|---|
| **1** | CloudFront + OAC + Custom Domain | `CloudFrontOriginConstruct` |
| **2** | MediaConvert Job Template + Step Functions | `VideoProcessingConstruct` |
| **3** | CloudFront Signed URLs + Cognito Auth | `AuthConstruct` |
| **4** | WAF + Monitoring + Dashboards | `SecurityConstruct`, `MonitoringConstruct` |
| **5** | MediaPackage + Multi‑Format Packaging | `PackagingConstruct` |
| **6** | CI/CD Pipeline + Canary Deployments | `PipelineConstruct` |
| **7** | Global Accelerator + Multi‑Region | `GlobalDeliveryConstruct` |

---

## 10. Conclusión

Este plan transforma tu proyecto de un **prototipo funcional** a una **plataforma de video CDN de nivel productivo**, comparable a servicios nativos de AWS como CloudFront + MediaPackage, con:

- **Disponibilidad**: 99.99% SLA (CloudFront + Global Accelerator)
- **Escalabilidad**: Step Functions + MediaConvert maneja miles de jobs concurrentes
- **Latencia**: < 100 ms en cualquier región gracias a CloudFront POPs + Origin Shield
- **Seguridad**: WAF + Signed URLs/Cookies + Cognito + (DRM opcional)
- **Cobertura de Formatos**: HLS + DASH + CMAF desde un solo origen
- **Costos Optimizados**: QVBR, Intelligent‑Tiering, PriceClass adecuado

### Primeros Pasos Recomendados

1. **Implementar CloudFront + OAC** (Sprint 1) – cambio de mayor impacto inmediato.
2. **Migrar transcodificación a MediaConvert** (Sprint 2) – elimina el cuello de botella de Lambda.
3. **Agregar WAF** (Sprint 3) – protege contra ataques DDoS básicos.

---

*Documento generado con base en el análisis del proyecto S3 Video Manager utilizando AWS CDK en Python.*
