# Plan Detallado de Distribucion de Contenido para Clientes Grandes

Version: 1.0
Fecha: 2026-07-23
Estado: Propuesta de arquitectura objetivo y roadmap de ejecucion

## 1. Contexto de negocio

Escenario objetivo:
- Cliente con 200 estaciones de servicio.
- Cada estacion con 10 a 16 equipos TPV Outdoor (OPT).
- Total estimado de endpoints: 2000 a 3200 OPT.

Objetivo operativo:
- Publicar campañas de video de forma centralizada.
- Distribuir cambios rapidamente a todos los OPT.
- Mantener control por estacion, grupo y dispositivo.
- Minimizar coste de transferencia y operacion.
- Garantizar resiliencia en entornos con conectividad variable.

## 2. Decisiones clave

Decisiones recomendadas:
1. No usar solo polling.
2. No usar solo webhook directo a cada OPT.
3. Usar modelo hibrido: push para notificar + pull para confirmar y descargar.
4. Distribuir archivos por CDN con versionado por release.
5. Mantener un backend local por estacion para coordinar OPT y reducir ruido operacional.

Razon tecnica:
- Push acelera tiempo de reaccion.
- Pull garantiza consistencia del estado real.
- CDN reduce carga al origen y mejora latencia.
- Versionado evita errores de cache y facilita rollback.

## 3. Arquitectura objetivo

Componentes:
- Control Plane (central): API de publicacion, catalogo, reglas de despliegue.
- Data Plane (distribucion): CloudFront + S3 privado como origen.
- Catalogo: DynamoDB con estado por release, estacion y dispositivo.
- Evento de cambio: EventBridge.
- Notificacion: SNS o AWS IoT Core MQTT.
- Backend local de estacion: agente que sincroniza, valida, descarga y activa en OPT.

Flujo de alto nivel:
1. Operador publica contenido y crea release.
2. Pipeline valida, versiona y publica manifiesto.
3. Evento notifica nuevo release a estaciones objetivo.
4. Backend local consulta manifiesto (pull), calcula delta y descarga solo cambios.
5. Backend local valida hash, activa de forma atomica y reporta estado.
6. OPT consumen contenido local o URL cacheada controlada por backend local.

## 4. Comparativa de estrategias de sincronizacion

### 4.1 Solo polling

Ventajas:
- Implementacion simple.
- Baja dependencia de infraestructura push.

Desventajas:
- Mucho trafico repetitivo hacia API.
- Mayor latencia para detectar cambios.
- Coste creciente con miles de equipos.

Uso recomendado:
- Solo como fallback de seguridad.

### 4.2 Solo webhook

Ventajas:
- Deteccion rapida de cambios.

Desventajas:
- Complejo en campo: NAT, firewall, IP dinamica, caidas intermitentes.
- Baja confiabilidad para entorno distribuido masivo.

Uso recomendado:
- No recomendado como mecanismo unico para OPT en campo.

### 4.3 Push por MQTT (IoT Core) + pull de manifiesto

Ventajas:
- Escalable a miles de dispositivos.
- Buen control por dispositivo/grupo.
- QoS y trazabilidad de eventos.

Desventajas:
- Mayor curva de adopcion inicial.

Uso recomendado:
- Opcion enterprise recomendada para madurez alta.

### 4.4 Push por SNS/EventBridge + pull de manifiesto

Ventajas:
- Rapido de implementar.
- Menor complejidad que IoT Core.
- Adecuado cuando ya existe backend de estacion.

Desventajas:
- Menor granularidad por dispositivo frente a IoT.

Uso recomendado:
- Mejor equilibrio para salida a produccion inicial.

## 5. Patron recomendado: Push + Pull con manifiesto versionado

Reglas del patron:
1. Push no transporta archivos, solo evento de cambio.
2. Pull consulta el manifiesto oficial y decide delta.
3. Cada release es inmutable y tiene identificador unico.
4. Descarga y activacion son transacciones separadas.
5. El rollback es nativo por version anterior.

Datos minimos por release:
- releaseId
- createdAt
- targetScope (global, region, estacion, grupo)
- assets con hash y tamano
- reglas de activacion
- politica de expiracion

## 6. Modelo de manifiesto

Campos recomendados:
- releaseId: identificador unico del release.
- catalogVersion: version semantica del catalogo.
- generatedAt: timestamp UTC.
- scope: region/estacion/grupo destino.
- assets: lista de objetos de contenido.
- activation: politica de activacion.
- integrity: hash global del manifiesto.

Estructura recomendada de cada asset:
- assetId
- path (ruta en CDN)
- sizeBytes
- contentType
- sha256
- ttlHint
- priority
- validFrom
- validTo

Comportamiento de cliente:
1. Guardar version local activa y version descargada.
2. Si releaseId no cambia, no descargar.
3. Si cambia, descargar solo assets faltantes o con hash distinto.
4. Activar solo cuando todos los hashes validen.

## 7. Contratos de API recomendados

### 7.1 Publicacion y releases (control interno)

- POST /releases
  - Crea release en estado draft.
- POST /releases/{releaseId}/publish
  - Publica release y emite evento push.
- POST /releases/{releaseId}/rollback
  - Marca release previo como activo para alcance indicado.

### 7.2 Sincronizacion para estaciones/backends locales

- GET /sync/manifest?stationId=...&group=...
  - Devuelve manifiesto efectivo para esa estacion.
- GET /sync/delta?stationId=...&fromRelease=...&toRelease=...
  - Devuelve solo cambios.
- POST /sync/status
  - Reporta estado: downloaded, verified, activated, failed.

### 7.3 Telemetria operativa

- POST /heartbeat
  - Ultima conexion, release activa, salud de agente.
- POST /events
  - Errores de descarga, validacion, activacion, playback.

## 8. Diseno CDN de nivel productivo

Configuracion recomendada de CloudFront:
1. S3 privado con OAC (no publico).
2. HTTPS obligatorio.
3. TTL alto para media inmutable versionada.
4. TTL corto para manifiestos y deltas.
5. Origin Shield habilitado en region principal.
6. Logging habilitado para analisis de cache hit ratio.

Practicas de cache:
- Inmutabilidad por ruta versionada, por ejemplo: /releases/{releaseId}/...
- Evitar invalidaciones masivas.
- Invalidar solo manifiestos si es estrictamente necesario.

Acceso seguro:
- Signed URLs o Signed Cookies de CloudFront para activos restringidos.
- JWT para APIs de control y sincronizacion.
- WAF con reglas managed + rate limit.

## 9. Backend local de estacion (agente de sincronizacion)

Responsabilidades:
1. Recibir notificacion push o ejecutar polling fallback.
2. Consultar manifiesto y delta.
3. Descargar en segundo plano.
4. Validar checksum.
5. Activar de forma atomica.
6. Mantener doble slot local A/B.
7. Reportar estado central.

Politica de tolerancia a fallos:
- Reintentos exponenciales con jitter.
- Cola local para operaciones pendientes.
- Degradacion controlada: continuar con contenido previo valido.
- Rollback automatico si falla activacion.

## 10. Estrategia de rollout

### Fase 1 (3-5 semanas): Base operativa

Entregables:
- CloudFront delante de S3 con OAC.
- Manifiesto versionado.
- Polling inteligente con backoff.
- Estado por estacion en DynamoDB.

Criterios de aceptacion:
- Publicacion detectada por todas las estaciones dentro de ventana definida.
- Sin impacto critico en latencia de reproduccion.

### Fase 2 (4-6 semanas): Notificacion push

Entregables:
- EventBridge + SNS (o IoT Core si se elige desde inicio).
- Endpoint de delta.
- Activacion atomica con rollback.

Criterios de aceptacion:
- Reduccion clara de tiempo de propagacion respecto a polling puro.
- Error de sincronizacion bajo objetivo SLO.

### Fase 3 (4-8 semanas): Escala enterprise

Entregables:
- Segmentacion por region/estacion/grupo.
- Canary rollout por porcentaje.
- Congelado de ventana horaria por sitio.
- Dashboard operativo y alertas.

Criterios de aceptacion:
- Rollout parcial y rollback validados en produccion.
- Observabilidad completa por release.

### Fase 4 (hardening): Seguridad y continuidad

Entregables:
- WAF avanzado.
- Controles de acceso por firma de CDN.
- Plan DR multi-region (si SLA lo exige).

Criterios de aceptacion:
- Prueba de recuperacion documentada.
- Cumplimiento de politicas de seguridad corporativa.

## 11. Observabilidad y SLO

Indicadores recomendados:
- Tiempo de propagacion por release (p50, p95, p99).
- Porcentaje de estaciones en version objetivo.
- Tasa de error de descarga y validacion.
- Cache hit ratio de CDN.
- Throughput de distribucion por hora.

SLO sugeridos iniciales:
1. 95% de estaciones sincronizadas en menos de 15 minutos.
2. Error de activacion menor a 1% por release.
3. Exito de rollback mayor a 99% cuando se ejecuta.

Alertas minimas:
- Estaciones sin heartbeat por encima de umbral.
- Release con fallos de validacion en cadena.
- Caida de cache hit ratio fuera de banda esperada.

## 12. Costes y optimizacion

Palancas de coste:
1. Maximizar cache hit ratio en CDN.
2. Descargar solo deltas.
3. Reducir polling cuando push esta estable.
4. Consolidar descargas por estacion via backend local.
5. Lifecycle en S3 para contenido historico.

Modelo de coste operativo:
- Coste de transferencia: dominado por egreso CDN.
- Coste de control plane: API, DynamoDB, mensajeria.
- Coste de observabilidad: logs, metricas y retencion.

Regla de oro:
- Invertir primero en buen manifiesto/delta y cache versionada suele ahorrar mas que optimizar micro-costes de API.

## 13. Riesgos y mitigaciones

Riesgo: conectividad irregular de estaciones.
- Mitigacion: fallback polling, cola local y rollback A/B.

Riesgo: contenido inconsistente en endpoints.
- Mitigacion: validacion hash obligatoria y activacion atomica.

Riesgo: sobrecarga por despliegues masivos simultaneos.
- Mitigacion: rollout por olas y ventanas horarias.

Riesgo: exposicion de origen.
- Mitigacion: S3 privado, OAC, firmas CDN, WAF.

## 14. Decisiones de implementacion para este proyecto

Para este repositorio y su estado actual, la recomendacion inicial es:
1. Mantener backend serverless actual como base de control.
2. Priorizar manifiesto versionado + CloudFront.
3. Introducir push con SNS/EventBridge en primera iteracion de notificacion.
4. Evaluar paso a IoT Core MQTT cuando se requiera granularidad por OPT.
5. Mantener polling como red de seguridad operativa.

## 15. Checklist de salida a produccion

Checklist tecnico:
- CloudFront activo con OAC.
- Manifiesto y delta validados.
- Agente local con A/B y rollback.
- Heartbeat y dashboard operativos.
- Alarmas en errores criticos de sync.

Checklist operativo:
- Runbook de incidentes de sincronizacion.
- Runbook de rollback por release.
- Procedimiento de despliegue por olas.
- Plan de comunicacion para ventanas de contenido.

Checklist de seguridad:
- Credenciales rotadas.
- JWT y/o firmas CDN con expiracion.
- WAF activo en borde.
- Auditoria de accesos a APIs de control.

## 16. Recomendacion final

La opcion mas robusta para 2000-3200 OPT no es elegir entre polling o webhook de forma binaria. La solucion mas estable es un diseno hibrido push + pull, con backend local por estacion, manifiesto inmutable, descarga delta y distribucion por CDN.

Este enfoque ofrece:
- rapidez de actualizacion,
- resiliencia en campo,
- control de version,
- capacidad de rollback,
- y coste sostenible a escala.
