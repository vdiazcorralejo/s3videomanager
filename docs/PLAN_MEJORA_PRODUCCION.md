# Plan de Mejora para Produccion - Video Content Delivery

> Version: 2.0
> Fecha: 2026-07-14
> Autor: Revision de Arquitectura AWS
> Estado actual del proyecto: MVP funcional - no apto para produccion
> Caso de uso objetivo: emision de video a pantallas con Windows Media Player embebido en aplicacion MFC C++ legacy
> Objetivo primario: minimizar coste operativo sin perder control, seguridad y capacidad de evolucion
> Esfuerzo total estimado: 5-7 sprints (10-14 semanas)

---

## Tabla de Contenidos

- [Resumen Ejecutivo](#resumen-ejecutivo)
- [Fase 0 - Adaptacion WMP + MFC Legacy + Coste Optimo](#fase-0---adaptacion-wmp--mfc-legacy--coste-optimo)
- [Fase 1 - Seguridad](#fase-1---seguridad)
- [Fase 2 - Resiliencia y Monitoreo](#fase-2---resiliencia-y-monitoreo)
- [Fase 3 - Escalabilidad y Diseno](#fase-3---escalabilidad-y-diseno)
- [Fase 4 - Operaciones y CI-CD](#fase-4---operaciones-y-ci-cd)
- [Analisis de Costes - Proyeccion Mensual](#analisis-de-costes---proyeccion-mensual)
- [Resumen de Estimacion](#resumen-de-estimacion)
- [Glosario de Buenas Practicas Aplicadas](#glosario-de-buenas-practicas-aplicadas)

---

## Resumen Ejecutivo

El sistema Video Content Delivery es una arquitectura serverless sobre AWS CDK en Python que hoy permite subir y descargar videos mediante URLs prefirmadas de S3, protegidas por API Gateway y un authorizer JWT.

Con el nuevo contexto de negocio, el objetivo ya no es un streaming web moderno para navegadores, sino la emision de contenido a dispositivos o pantallas que ejecutan una aplicacion MFC C++ legacy con Windows Media Player embebido. Ese detalle cambia de forma importante la arquitectura objetivo.

Hallazgo principal: para este caso de uso no hace falta construir una plataforma HLS/DASH completa. Windows Media Player puede reproducir MP4 por descarga progresiva HTTP de forma nativa, y S3 ya soporta range requests. Eso elimina de entrada los componentes mas caros de una plataforma de streaming clasica, como MediaConvert, MediaPackage y parte de la complejidad de CDN avanzada.

La conclusion es clara:

1. La arquitectura actual esta mas cerca de servir el caso real de lo que parecia.
2. El hueco principal no esta en el playback, sino en catalogo, metadatos, miniaturas, seguridad operativa y control del ciclo de vida.
3. La optimizacion de coste exige mantener la solucion simple: MP4 directo, S3, API ligera, catalogo en DynamoDB y procesado minimo.

Este documento actualiza el plan de mejora con una Fase 0 especifica para el escenario WMP/MFC, y reordena las fases restantes para que el camino a produccion sea tecnicamente correcto y economicamente razonable.

---

## Fase 0 - Adaptacion WMP + MFC Legacy + Coste Optimo

> Prioridad: critica para el caso de uso real
> Esfuerzo estimado: 2 sprints (4 semanas)

### 0.0 Diagnostico Arquitectonico

El proyecto actual sirve archivos. No sirve todavia un catalogo operativo para pantallas. Para el escenario WMP embebido esto no es un problema de streaming avanzado, sino de producto de distribucion de contenido.

Capacidades actuales que ya encajan:

| Necesidad | Estado actual | Comentario |
| --- | --- | --- |
| Obtener URL de reproduccion | Parcialmente cubierta | `generate_url_pre` ya devuelve presigned URL |
| Reproducir MP4 por HTTP | Compatible | WMP soporta descarga progresiva |
| Autenticacion de acceso al API | Cubierta de forma basica | JWT custom authorizer existente |
| Almacenamiento barato y simple | Cubierto | S3 es suficiente para VOD basico |

Huecos reales a cubrir:

| Necesidad | Estado actual | Accion requerida |
| --- | --- | --- |
| Catalogo navegable para la app MFC | No existe | Nuevo endpoint `GET /catalog` |
| Metadatos por video | Muy limitados | Redisenar esquema DynamoDB |
| Miniaturas | No existe | Generacion serverless o miniatura generica |
| Flujo robusto de reproduccion | Incompleto | Ajustar presigned URL para playback |
| Politica de coste | No existe | Lifecycle, tiering y simplificacion |

Decisiones de arquitectura para este escenario:

1. Mantener MP4 como formato principal de entrega.
2. Exigir H.264 + AAC como formato objetivo de subida para compatibilidad con WMP.
3. No introducir HLS, DASH, MediaConvert ni MediaPackage salvo requisito nuevo de negocio.
4. Mantener CloudFront como opcion, no como componente obligatorio.
5. Priorizar simplicidad operativa y coste minimo por encima de elasticidad sofisticada.

---

### 0.1 Modelo de Consumo de la App MFC

La app legacy necesita un flujo simple, estable y controlado. El flujo recomendado es este:

1. La app obtiene un JWT contra `POST /token`.
2. La app consulta `GET /catalog` y recibe lista de contenidos listos para reproducir.
3. El usuario o proceso local selecciona un item.
4. La app solicita `GET /geturl?action=get_playback_url&key=<file>` con el JWT.
5. La API devuelve una presigned URL de S3 optimizada para playback.
6. La app asigna esa URL al reproductor WMP embebido.

Ventajas de este flujo:

1. WMP no necesita enviar cabeceras custom al origen.
2. La API mantiene el control de autorizacion antes de emitir la URL.
3. La URL de reproduccion expira sola y reduce superficie de exposicion.
4. El cliente legacy no necesita logica moderna de player.

---

### 0.2 Endpoint de Catalogo: `GET /catalog`

Problema: el endpoint actual `list_files` solo devuelve nombres de objetos del bucket. Eso no es un catalogo util para una app operativa.

Objetivo funcional del catalogo:

1. Devolver solo items listos para reproducir.
2. Incluir metadatos utiles para UI o logica de reproduccion.
3. Permitir paginacion y filtros basicos.
4. Evitar lecturas directas del bucket desde el cliente.

Respuesta objetivo:

```json
{
  "videos": [
    {
      "id": "vid-abc123",
      "title": "Promo Verano 2026",
      "fileName": "promo-verano-2026.mp4",
      "status": "ready",
      "durationSeconds": 32,
      "sizeBytes": 52428800,
      "thumbnailUrl": "https://bucket.s3.amazonaws.com/thumbnails/promo-verano-2026.jpg",
      "uploadDate": "2026-07-10T14:30:00Z",
      "contentType": "video/mp4"
    }
  ],
  "pageSize": 20,
  "lastEvaluatedKey": null
}
```

Esquema DynamoDB recomendado:

| PK | SK | Campos |
| --- | --- | --- |
| `catalog` | `videoId` | `title`, `fileName`, `status`, `durationSeconds`, `sizeBytes`, `thumbnailKey`, `uploadDate`, `contentType` |

Indices recomendados:

| Indice | PK | SK | Uso |
| --- | --- | --- | --- |
| `StatusIndex` | `catalog` | `status` | listar contenidos listos o fallidos |
| `UploadDateIndex` | `catalog` | `uploadDate` | ordenar por recientes |

Requisitos del endpoint:

1. Soportar `pageSize` con maximo fijo, por ejemplo 20 o 50.
2. Soportar `lastEvaluatedKey` para paginacion real.
3. Permitir filtro por `status=ready` por defecto.
4. Nunca consultar S3 para listar en tiempo real desde el endpoint.

Tareas:

- [x] Crear Lambda `CatalogFunction`
- [x] Crear `GET /catalog` protegido por JWT
- [x] Redisenar DynamoDB a item por video
- [x] Anadir GSI `StatusIndex`
- [x] Anadir paginacion con `LastEvaluatedKey`

---

### 0.3 Adaptar `generate_url_pre` para Playback Real

Problema: la Lambda actual genera URLs de descarga, pero no esta ajustada de forma explicita para el comportamiento de playback de WMP.

Objetivo:

1. Entregar URL valida para reproducir y no solo descargar.
2. Fijar `Content-Type` correcto segun extension.
3. Devolver `Content-Disposition: inline`.
4. Usar expiracion suficiente para sesiones largas.

Comportamiento recomendado:

```python
def generate_playback_url(event):
    key = event['queryStringParameters'].get('key')
    bucket_name = os.environ['BUCKET_NAME']

    content_types = {
        '.mp4': 'video/mp4',
        '.wmv': 'video/x-ms-wmv',
        '.avi': 'video/x-msvideo',
        '.webm': 'video/webm'
    }

    ext = os.path.splitext(key)[1].lower()
    content_type = content_types.get(ext, 'application/octet-stream')

    url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': bucket_name,
            'Key': key,
            'ResponseContentType': content_type,
            'ResponseContentDisposition': 'inline'
        },
        ExpiresIn=86400
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'url': url, 'contentType': content_type, 'expiresIn': 86400})
    }
```

Notas operativas:

1. Usar 24 horas como valor inicial de expiracion si la reproduccion puede ser larga o la pantalla puede reintentar.
2. Si la URL se comparte entre procesos o cache local, bajar a 1-4 horas y refrescar desde la app.
3. Validar al menos extensiones `.mp4` y `.wmv` si existen dispositivos antiguos.
4. Confirmar en entorno real que el control WMP usa range requests correctamente.

Tareas:

- [x] Crear `action=get_playback_url`
- [x] Diferenciar descarga de playback si se mantienen ambas acciones
- [x] Mapear content type por extension
- [x] Configurar expiracion de playback mas larga que la de descarga puntual
- [ ] Validar reproduccion real en la app MFC

---

### 0.4 Estrategia de Miniaturas con Coste Minimo

Problema: una pantalla o consola operativa necesita una referencia visual, pero no compensa desplegar un pipeline caro solo para thumbnails.

Opciones, ordenadas por coste:

| Opcion | Coste | Complejidad | Recomendacion |
| --- | --- | --- | --- |
| Miniatura generica por categoria | minimo | muy baja | buena para primera salida |
| Lambda + FFmpeg extrae 1 frame | bajo | media | mejor equilibrio |
| MediaConvert genera thumbnails | medio-alto | media | no recomendado para este caso |

Ruta recomendada:

1. Primera iteracion: miniatura generica si el time-to-market manda.
2. Segunda iteracion: Lambda con FFmpeg layer para sacar un frame fijo.

Ejemplo de procesamiento barato:

```python
subprocess.run([
    '/opt/ffmpeg/ffmpeg', '-y',
    '-ss', '5',
    '-i', input_path,
    '-vframes', '1',
    '-vf', 'scale=320:-1',
    '-q:v', '3',
    output_path
], check=True, timeout=30)
```

Riesgos y controles:

1. No descargar videos enormes completos si no hace falta para miniatura.
2. Ajustar memoria y timeout de Lambda para FFmpeg.
3. Limpiar `/tmp` siempre.
4. Si el video no permite frame en segundo 5, caer a segundo 1.

Tareas:

- [ ] Decidir entre thumbnail generica o extraccion real en Fase 0
- [ ] Si se usa FFmpeg, crear `GenerateThumbnailFunction`
- [ ] Guardar miniaturas en prefijo `thumbnails/`
- [ ] Persistir `thumbnailKey` en DynamoDB

---

### 0.5 Requisitos de Ingesta para Compatibilidad con WMP

Problema: el ahorro real se consigue si no hay transcodificacion. Eso solo es viable si se controla el formato de subida.

Politica de ingest a imponer:

1. Formato contenedor principal: MP4.
2. Video codec: H.264.
3. Audio codec: AAC.
4. Tamano maximo por archivo definido por negocio.
5. Nombre de archivo normalizado para evitar caracteres conflictivos.

Validaciones necesarias:

1. Validacion por extension en la API antes de generar upload URL.
2. Validacion por `ContentType` esperado.
3. Si el negocio necesita mas control, validacion post-upload de metadatos con `ffprobe` o `mediainfo` en Lambda.

Si no se controla esto, el riesgo es claro: archivos validos para S3 pero no reproducibles en WMP, lo que obliga despues a introducir transcodificacion y dispara el coste.

Tareas:

- [ ] Restringir upload a extensiones soportadas
- [ ] Documentar formato obligado para proveedores de contenido
- [ ] Evaluar validacion post-upload de codec real solo si hay incidencias

---

### 0.6 Estrategia de Coste de Almacenamiento y Transferencia

Objetivo: mantener el gasto estable incluso si crece el catalogo.

Medidas recomendadas:

1. Activar S3 Intelligent-Tiering si el catalogo tiene patrones de acceso irregulares.
2. Mover contenido frio a Glacier Instant Retrieval solo si el negocio tolera pequena latencia extra y recuperacion condicionada.
3. No activar CloudFront por defecto si todas las pantallas estan en la misma region o misma geografia.
4. Reducir consultas innecesarias al catalogo con cache local en la app MFC cuando sea posible.

Reglas S3 recomendadas:

```python
bucket.add_lifecycle_rule(
    id='IntelligentTiering',
    transitions=[
        s3.Transition(
            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
            transition_after=Duration.days(0)
        )
    ]
)

bucket.add_lifecycle_rule(
    id='ArchiveOldVideos',
    transitions=[
        s3.Transition(
            storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
            transition_after=Duration.days(90)
        )
    ],
    prefix='videos/'
)
```

Decision economica importante:

1. Si el contenido se reproduce sobre todo en una sede o pocas sedes, S3 directo es mejor.
2. Si hay muchas sedes geograficamente dispersas, CloudFront puede compensar por latencia aunque suba algo el coste.
3. Si el contenido rota poco, el mayor coste vendra de transferencia, no de computo.

Tareas:

- [ ] Activar lifecycle rules en S3
- [ ] Medir patron real de accesos antes de introducir CDN
- [ ] Evaluar cache de catalogo en cliente

---

## Fase 1 - Seguridad

> Prioridad: inmediata - bloqueante para produccion
> Esfuerzo estimado: 1 sprint (2 semanas)

### 1.1 Externalizar `SECRET_KEY` a AWS Secrets Manager

Problema: la clave JWT esta hardcodeada en codigo.

Solucion:

```python
import boto3
import json
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def get_secret():
    secret_name = os.environ['JWT_SECRET_NAME']
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])['JWT_SECRET_KEY']
```

Tareas:

- [ ] Crear recurso `Secret` en CDK
- [ ] Otorgar `secretsmanager:GetSecretValue` solo a `auth` y `token_generator`
- [ ] Pasar `JWT_SECRET_NAME` por variables de entorno
- [ ] Cachear el secreto en memoria

---

### 1.2 Cambiar `RemovalPolicy` de `DESTROY` a `RETAIN`

Problema: un `cdk destroy` destruiria contenido y metadatos.

Tareas:

- [ ] Cambiar `RemovalPolicy` a `RETAIN` en S3, DynamoDB y log groups de produccion
- [ ] Eliminar `auto_delete_objects=True`
- [ ] Definir procedimiento seguro de limpieza manual

---

### 1.3 Principio de Minimo Privilegio en IAM

Problema: `grant_full_access()` es excesivo.

Tareas:

- [ ] Cambiar `grant_full_access` por `grant_read_write_data`
- [ ] Revisar permisos S3 por Lambda
- [ ] Quitar permisos innecesarios al authorizer

---

### 1.4 Anadir AWS WAF al API Gateway

Problema: API expuesta sin protecciones basicas de capa 7.

Tareas:

- [ ] Crear `WafConstruct`
- [ ] Activar `AWSManagedRulesCommonRuleSet`
- [ ] Activar `AWSManagedRulesSQLiRuleSet`
- [ ] Configurar rate limit

Nota: si el sistema va a operar solo en red controlada o VPN privada, puede estudiarse dejar WAF fuera en una primera fase para reducir coste. Si el API es publico en Internet, WAF sigue siendo recomendable.

---

### 1.5 Endurecimiento de S3

Tareas:

- [ ] Activar `enforce_ssl=True`
- [ ] Activar cifrado gestionado
- [ ] Configurar access logs o CloudTrail data events segun coste y necesidad de auditoria
- [ ] Mantener bucket privado y sin acceso publico

---

## Fase 2 - Resiliencia y Monitoreo

> Prioridad: alta
> Esfuerzo estimado: 1 sprint (2 semanas)

### 2.1 Pasar de S3 -> Lambda directa a S3 -> SQS -> Lambda

Problema: el trigger directo desde S3 complica reintentos, control de errores y DLQ.

Patron recomendado:

```python
dlq = sqs.Queue(self, 'ProcessVideoDLQ', retention_period=Duration.days(14))

main_queue = sqs.Queue(
    self,
    'ProcessVideoQueue',
    dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3)
)
```

Beneficios:

1. Reintentos controlados.
2. Mensajes fallidos visibles.
3. Menor acoplamiento operativo.

Tareas:

- [ ] Migrar a S3 -> SQS -> Lambda
- [ ] Configurar DLQ
- [ ] Ajustar visibility timeout

---

### 2.2 Alarmas CloudWatch

Alarmas minimas:

| Alarma | Umbral |
| --- | --- |
| API Gateway 5XX | >= 1 |
| Lambda Errors | >= 1 |
| Lambda Duration p99 | > 80% timeout |
| Lambda Throttles | >= 1 |
| DynamoDB throttles | >= 1 |
| DLQ messages visibles | >= 1 |

Tareas:

- [ ] Crear topic SNS
- [ ] Crear alarmas base
- [ ] Crear dashboard operacional

---

### 2.3 Ajuste de Timeouts y Memoria

Dimensionado recomendado:

| Lambda | Timeout | Memoria |
| --- | --- | --- |
| `GetPresignedUrlFunction` | 10s | 256MB |
| `apigatewayAuthorizer` | 5s | 256MB |
| `ProcessVideoFunction` | 30s | 512MB |
| `CatalogFunction` | 10s | 256MB |
| `GenerateThumbnailFunction` | 60s | 1024MB |

Tareas:

- [ ] Parametrizar timeout y memoria en `LambdaConstruct`
- [ ] Evaluar `ARM_64` para bajar coste Lambda

---

### 2.4 Retencion de Logs

Tareas:

- [ ] Produccion: 3 meses o 1 ano segun compliance
- [ ] Desarrollo: 1 semana
- [ ] Hacer configurable por stage

---

## Fase 3 - Escalabilidad y Diseno

> Prioridad: media
> Esfuerzo estimado: 1-2 sprints (2-4 semanas)

### 3.1 Refactor de `process_video` a modelo incremental

Problema: hoy escanea todo el bucket y reescribe lista completa.

Nuevo enfoque:

1. Un upload genera un item de catalogo.
2. No se lista el bucket completo.
3. El estado pasa de `processing` a `ready`.

Tareas:

- [ ] Persistir un item por video
- [ ] Anadir `status`
- [ ] Registrar `title`, `sizeBytes`, `uploadDate`, `thumbnailKey`

---

### 3.2 Exponer `POST /token`

Problema: la Lambda generadora de token no esta conectada.

Tareas:

- [ ] Exponer `POST /token`
- [ ] Proteger con API key o policy de red si aplica
- [ ] Limitar frecuencia por IP o dispositivo

---

### 3.3 Mejorar robustez de `generate_url_pre`

Tareas:

- [ ] Separar acciones `get_upload_url`, `get_download_url`, `get_playback_url`
- [ ] Validar extensiones permitidas
- [ ] Validar tamano maximo en upload
- [ ] Unificar respuestas y errores

---

### 3.4 Normalizar respuestas compartidas

Tareas:

- [ ] Crear modulo `shared/responses.py`
- [ ] Centralizar cabeceras CORS
- [ ] Evitar `Access-Control-Allow-Origin: *` en produccion

---

### 3.5 CloudFront como opcion, no como obligacion

CloudFront solo deberia entrar si se cumple al menos una de estas condiciones:

1. Pantallas distribuidas en varias regiones.
2. Latencia perceptible desde S3 directo.
3. Necesidad de cache geografica.

Si no se cumplen, mantener S3 directo evita coste y complejidad.

Tareas:

- [ ] Medir latencia real de playback antes de decidir CDN
- [ ] Si entra CDN, usar OAC y origen privado

---

## Fase 4 - Operaciones y CI-CD

> Prioridad: media-baja
> Esfuerzo estimado: 1 sprint (2 semanas)

### 4.1 Multiples entornos

Tareas:

- [ ] Definir `dev`, `staging`, `prod`
- [ ] Parametrizar dominios, retencion, WAF y policies por stage
- [ ] Evitar valores hardcodeados de region y bucket name

---

### 4.2 Pipeline CI-CD

Tareas:

- [ ] Crear pipeline CDK
- [ ] Sintesis automatica
- [ ] Despliegue a staging con pruebas
- [ ] Aprobacion manual a produccion

---

### 4.3 Tests reales

Cobertura minima deseable:

1. Tests CDK de recursos creados.
2. Tests unitarios de `auth`, `generate_url_pre`, `process_video`, `catalog`.
3. Tests de integracion sobre endpoints desplegados.

Tareas:

- [ ] Anadir tests unitarios
- [ ] Anadir tests de integracion
- [ ] Validar flujos token -> catalogo -> playback URL

---

### 4.4 CDK Nag

Tareas:

- [ ] Integrar `cdk-nag`
- [ ] Revisar findings y documentar excepciones justificadas

---

### 4.5 Trazabilidad con X-Ray

Tareas:

- [ ] Activar tracing en API Gateway y Lambdas clave
- [ ] Verificar trazas en el flujo de catalogo y playback URL

---

## Analisis de Costes - Proyeccion Mensual

### Supuestos

| Variable | Escenario conservador | Escenario optimista |
| --- | --- | --- |
| Videos en catalogo | 500 | 200 |
| Tamano medio por video | 200 MB | 100 MB |
| Reproducciones por dia por pantalla | 50 | 20 |
| Numero de pantallas | 50 | 10 |
| Consultas catalogo por dia | 100 | 20 |

### Estimacion

| Servicio | Conservador | Optimista |
| --- | --- | --- |
| S3 almacenamiento | 2.30 USD | 2.30 USD |
| S3 transferencia | 27.00 USD | 5.40 USD |
| S3 requests | 1.00 USD | 0.20 USD |
| Lambda invocaciones y duracion | 0.50 USD | 0.10 USD |
| API Gateway | 1.00 USD | 0.20 USD |
| DynamoDB | ~0 USD | ~0 USD |
| CloudWatch logs | 0.50 USD | 0.50 USD |
| Secrets Manager | 0.40 USD | 0.40 USD |
| WAF | 5.00 USD | 5.00 USD |
| Total estimado | ~38 USD/mes | ~14 USD/mes |

Lectura correcta de coste:

1. El coste dominante sera transferencia S3, no computo.
2. Si el API esta restringido a una red controlada, el WAF puede revisarse como palanca de ahorro, aunque implica mas riesgo.
3. El uso de MediaConvert o MediaPackage dispararia el coste y no esta justificado hoy.

---

## Resumen de Estimacion

| Fase | Nombre | Esfuerzo | Prioridad |
| --- | --- | --- | --- |
| 0 | Adaptacion WMP/MFC + coste optimo | 4 semanas | Critica |
| 1 | Seguridad | 2 semanas | Critica |
| 2 | Resiliencia | 2 semanas | Alta |
| 3 | Escalabilidad y diseno | 2-4 semanas | Media |
| 4 | Operaciones y CI-CD | 2 semanas | Media-Baja |
| Total | | 12-14 semanas | |

Secuencia recomendada de entrega:

1. Fase 0 y partes minimas de Fase 1 para poder pilotar.
2. Fase 2 antes de crecimiento real del parque de pantallas.
3. Fase 3 solo en lo estrictamente necesario para escalar.
4. Fase 4 para profesionalizar el despliegue.

---

## Glosario de Buenas Practicas Aplicadas

| Principio | Aplicacion en este plan |
| --- | --- |
| Least Privilege | Reducir permisos IAM al minimo necesario |
| Secrets Management | Externalizar claves a Secrets Manager |
| Cost Optimization First | Evitar transcodificacion y CDN innecesarios |
| Progressive Delivery | MP4 progresivo compatible con WMP |
| Infrastructure as Code | Todo definido con CDK |
| Observability | Alarmas, logs, dashboard y trazas |
| Fail-Safe | DLQ y politicas de retencion adecuadas |
| Simplicity Over Fashion | Arquitectura simple adaptada al cliente legacy |

---

Nota final: para el contexto 2026, este proyecto puede convertirse en una solucion valida y muy barata para emision de contenido en pantallas si se mantiene disciplinado en dos decisiones: no sobredisenar el playback y controlar estrictamente el formato de contenido de entrada. Si el negocio evoluciona hacia multiplataforma, navegadores, movil o streaming adaptativo, entonces si habra que replantear la arquitectura con una capa media especifica.
