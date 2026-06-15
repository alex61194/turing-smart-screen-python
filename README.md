# Turing Smart Screen - Python System Monitor (NVIDIA, RTSS & LHM Fork)

Este repositorio es un fork optimizado y corregido del proyecto original de `mathoudebine/turing-smart-screen-python`. Está enfocado en ofrecer una alternativa de código abierto, ligera y universal para monitorizar los recursos del sistema en pantallas secundarias IPS USB-C (Turing / TURZX de 3.5" y compatibles) bajo entornos Windows, solucionando las limitaciones de lectura de software tradicionales.

## 🌟 El Motivo de este Fork (La arquitectura de telemetría)

Las librerías de monitorización estándar y herramientas como **LibreHardwareMonitor** son excelentes para obtener datos de hardware puros (temperaturas, cargas, voltajes y frecuencias de CPU/GPU), pero **carecen por completo de soporte para leer los FPS (fotogramas por segundo)** en juegos y entornos renderizados por hardware NVIDIA.

Para solucionar esto, este fork reestructura el código de recolección de datos en Windows para trabajar mediante una configuración híbrida de alto rendimiento:
1. **LibreHardwareMonitor:** Se encarga de extraer toda la telemetría térmica, porcentajes de uso y frecuencias del procesador y la gráfica.
2. **RTSS (RivaTuner Statistics Server):** El script se conecta mediante Python al servidor de RivaTuner para capturar de forma nativa e inyectar los FPS reales de cualquier aplicación en primer plano.

Al unificar ambas fuentes de datos directamente a través de código en Python (en lugar de depender de pesados ejecutables cerrados del fabricante), se consigue un monitor de sistema fluido, exacto, en tiempo real y sin retardo de hilos (*multithreading*).

## 🛠️ Características de este Fork

- **Soporte de FPS mediante RTSS:** Integración nativa con RivaTuner Statistics Server para mostrar los FPS en tiempo real de tu GPU NVIDIA.
- **Telemetría Completa con LHM:** Monitorización precisa de temperaturas, uso de memoria, almacenamiento y reloj del sistema.
- **Portabilidad Limpia:** Ejecución nativa en Python 3.9+, transparente y sin residuos en el sistema operativo.


## 📋 Requisitos Previos

1. Tener instalado **Python 3.9 o superior** en Windows (asegúrate de marcar la casilla *"Add Python to PATH"* en el instalador).
2. Tener **RivaTuner Statistics Server (RTSS)** ejecutándose en segundo plano (suele venir integrado junto a MSI Afterburner) para la telemetría de FPS.
3. Asegurar el acceso o ejecución de **LibreHardwareMonitor** en tu sistema para la lectura del resto de sensores.
