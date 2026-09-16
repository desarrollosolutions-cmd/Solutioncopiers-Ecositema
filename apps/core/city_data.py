"""Contenido de las páginas de cobertura por ciudad.

Sigue el mismo patrón que ``_SOLUTION_META`` en ``apps/core/views.py``: un
diccionario Python plano, sin modelo de base de datos, porque es un conjunto
pequeño y conocido de páginas (no un catálogo abierto administrable desde el
admin). "tier" define qué tan honesto podemos ser sobre el tipo de cobertura:

- "presencial": Valle de Aburrá / Antioquia, donde hay atención técnica en
  sitio real, respaldado por el volumen real de clientes en esas ciudades.
- "nacional": el resto del país, donde el modelo real es despacho de equipos
  e insumos desde Medellín + técnicos aliados locales (no oficina propia).
"""
from __future__ import annotations

COVERAGE_NOTES = {
    "presencial": (
        "Atención técnica 100% presencial: visitas en sitio, mantenimiento "
        "preventivo y correctivo, y entrega o recolección de equipos sin "
        "costos adicionales de desplazamiento dentro del Valle de Aburrá."
    ),
    "nacional": (
        "Despachamos equipos e insumos a nivel nacional desde Medellín, y "
        "coordinamos el servicio técnico en sitio con aliados locales "
        "certificados en tu ciudad."
    ),
}

CITY_PAGES = {
    "itagui": {
        "order": 1,
        "name": "Itagüí",
        "region": "Valle de Aburrá, Antioquia",
        "tier": "presencial",
        "h1": "Alquiler y Venta de Fotocopiadoras en Itagüí",
        "meta_title": "Alquiler de Fotocopiadoras en Itagüí | Solution Copiers",
        "meta_description": (
            "Alquiler y venta de fotocopiadoras Ricoh en Itagüí, con "
            "mantenimiento, tóner y servicio técnico presencial incluido. "
            "Sin inversión inicial."
        ),
        "intro": (
            "Itagüí es uno de los principales polos textiles e industriales "
            "del Valle de Aburrá, con una alta concentración de empresas "
            "manufactureras y de confección que dependen de una operación "
            "documental sin interrupciones. Desde Medellín atendemos Itagüí "
            "con visitas técnicas presenciales, entrega e instalación de "
            "equipos y recolección de insumos sin costos adicionales de "
            "desplazamiento."
        ),
        "zones": ["Centro", "Zona Industrial", "San Pío", "Santa María"],
    },
    "envigado": {
        "order": 2,
        "name": "Envigado",
        "region": "Valle de Aburrá, Antioquia",
        "tier": "presencial",
        "h1": "Alquiler y Venta de Fotocopiadoras en Envigado",
        "meta_title": "Alquiler de Fotocopiadoras en Envigado | Solution Copiers",
        "meta_description": (
            "Alquiler y venta de fotocopiadoras Ricoh en Envigado, con "
            "mantenimiento, tóner y servicio técnico presencial incluido. "
            "Sin inversión inicial."
        ),
        "intro": (
            "Envigado concentra una de las zonas empresariales y "
            "corporativas más activas al sur de Medellín, con oficinas de "
            "servicios, sedes administrativas y comercio consolidado. "
            "Prestamos servicio presencial en Envigado con instalación, "
            "mantenimiento preventivo y correctivo, y reposición de tóner "
            "sin que tu equipo tenga que desplazarse."
        ),
        "zones": ["El Dorado", "Zona Rosa", "La Magnolia", "Loma del Escobero"],
    },
    "sabaneta": {
        "order": 3,
        "name": "Sabaneta",
        "region": "Valle de Aburrá, Antioquia",
        "tier": "presencial",
        "h1": "Alquiler y Venta de Fotocopiadoras en Sabaneta",
        "meta_title": "Alquiler de Fotocopiadoras en Sabaneta | Solution Copiers",
        "meta_description": (
            "Alquiler y venta de fotocopiadoras Ricoh en Sabaneta, con "
            "mantenimiento, tóner y servicio técnico presencial incluido. "
            "Sin inversión inicial."
        ),
        "intro": (
            "Sabaneta es uno de los municipios con mayor densidad de "
            "oficinas y sedes empresariales del sur del Valle de Aburrá, en "
            "pleno crecimiento comercial y financiero. Atendemos Sabaneta "
            "de forma presencial, con los mismos tiempos de respuesta que "
            "en Medellín para instalación, mantenimiento y soporte técnico."
        ),
        "zones": ["Centro", "Vegas del Poblado", "Zona Financiera"],
    },
    "bello": {
        "order": 4,
        "name": "Bello",
        "region": "Valle de Aburrá, Antioquia",
        "tier": "presencial",
        "h1": "Alquiler y Venta de Fotocopiadoras en Bello",
        "meta_title": "Alquiler de Fotocopiadoras en Bello | Solution Copiers",
        "meta_description": (
            "Alquiler y venta de fotocopiadoras Ricoh en Bello, con "
            "mantenimiento, tóner y servicio técnico presencial incluido. "
            "Sin inversión inicial."
        ),
        "intro": (
            "Bello es el segundo municipio más poblado de Antioquia y un "
            "centro industrial y comercial clave al norte del Valle de "
            "Aburrá. Ofrecemos servicio presencial completo en Bello: "
            "entrega e instalación de equipos, mantenimiento preventivo y "
            "correctivo, y suministro continuo de tóner e insumos "
            "originales."
        ),
        "zones": ["Niquía", "Zona Industrial", "Café Madrid"],
    },
    "la-estrella": {
        "order": 5,
        "name": "La Estrella",
        "region": "Valle de Aburrá, Antioquia",
        "tier": "presencial",
        "h1": "Alquiler y Venta de Fotocopiadoras en La Estrella",
        "meta_title": "Alquiler de Fotocopiadoras en La Estrella | SC",
        "meta_description": (
            "Alquiler y venta de fotocopiadoras Ricoh en La Estrella, con "
            "mantenimiento, tóner y servicio técnico presencial incluido. "
            "Sin inversión inicial."
        ),
        "intro": (
            "La Estrella combina una vocación industrial y logística "
            "creciente con cercanía al Aeropuerto Olaya Herrera, lo que la "
            "convierte en un punto estratégico para empresas de transporte, "
            "bodegaje y manufactura. Cubrimos La Estrella con atención "
            "técnica presencial, sin costos adicionales de desplazamiento "
            "dentro del Valle de Aburrá."
        ),
        "zones": ["Pueblo Viejo", "La Tablaza", "Ancón Sur"],
    },
    "bogota": {
        "order": 6,
        "name": "Bogotá",
        "region": "Bogotá D.C., Cundinamarca",
        "tier": "nacional",
        "h1": "Alquiler y Venta de Fotocopiadoras en Bogotá",
        "meta_title": "Alquiler de Fotocopiadoras en Bogotá | Solution Copiers",
        "meta_description": (
            "Alquiler y venta de fotocopiadoras Ricoh en Bogotá, con "
            "despacho de equipos e insumos desde Medellín y servicio "
            "técnico con aliados locales."
        ),
        "intro": (
            "Como capital del país, Bogotá concentra la mayor densidad de "
            "empresas de Colombia y una demanda constante de soluciones de "
            "impresión confiables. Despachamos equipos e insumos a Bogotá "
            "desde nuestra sede en Medellín y coordinamos el servicio "
            "técnico en sitio con aliados locales certificados, para que tu "
            "operación documental no dependa de la distancia."
        ),
        "zones": [],
    },
}
