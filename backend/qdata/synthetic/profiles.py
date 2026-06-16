VENTAS_PROFILE = {
    "columns": [
        {"name": "id", "type": "int", "min": 1, "max": 100000},
        {"name": "cliente", "type": "name"},
        {"name": "email", "type": "email"},
        {"name": "producto", "type": "choice",
         "values": ["Laptop", "Mouse", "Teclado", "Monitor", "Audífonos", "Webcam", "Tablet", "Impresora"]},
        {"name": "cantidad", "type": "int", "min": 1, "max": 10},
        {"name": "precio_unitario", "type": "float", "min": 50, "max": 5000, "mean": 800, "std": 300},
        {"name": "fecha", "type": "date", "start": "2024-01-01", "end": "2025-12-31"},
        {"name": "region", "type": "choice",
         "values": ["Norte", "Sur", "Este", "Oeste", "Centro"]},
        {"name": "categoria", "type": "choice",
         "values": ["Electrónica", "Computación", "Periféricos", "Accesorios"]},
    ]
}

RH_PROFILE = {
    "columns": [
        {"name": "id_empleado", "type": "int", "min": 1, "max": 50000},
        {"name": "nombre", "type": "name"},
        {"name": "email", "type": "email"},
        {"name": "departamento", "type": "choice",
         "values": ["TI", "Ventas", "RH", "Finanzas", "Marketing", "Operaciones", "Legal"]},
        {"name": "puesto", "type": "choice",
         "values": ["Analista", "Coordinador", "Gerente", "Director", "Practicante"]},
        {"name": "salario", "type": "float", "min": 15000, "max": 150000, "mean": 45000, "std": 20000},
        {"name": "fecha_ingreso", "type": "date", "start": "2020-01-01", "end": "2025-06-01"},
        {"name": "edad", "type": "int", "min": 20, "max": 70},
        {"name": "genero", "type": "choice", "values": ["M", "F", "Otro"]},
    ]
}

FINANZAS_PROFILE = {
    "columns": [
        {"name": "id_transaccion", "type": "int", "min": 1, "max": 200000},
        {"name": "cuenta", "type": "string", "prefix": "CTA-", "length": 8},
        {"name": "tipo", "type": "choice", "values": ["Crédito", "Débito", "Transferencia", "Nómina"]},
        {"name": "monto", "type": "float", "min": -50000, "max": 200000, "mean": 5000, "std": 10000},
        {"name": "fecha", "type": "date", "start": "2024-06-01", "end": "2025-06-01"},
        {"name": "sucursal", "type": "choice",
         "values": ["CDMX Centro", "CDMX Sur", "Monterrey", "Guadalajara", "Querétaro", "Cancún"]},
        {"name": "estatus", "type": "choice", "values": ["Completada", "Pendiente", "Rechazada", "Reembolsada"]},
    ]
}

SALUD_PROFILE = {
    "columns": [
        {"name": "id_paciente", "type": "int", "min": 1, "max": 100000},
        {"name": "nombre", "type": "name"},
        {"name": "edad", "type": "int", "min": 0, "max": 100},
        {"name": "genero", "type": "choice", "values": ["M", "F"]},
        {"name": "tipo_sangre", "type": "choice",
         "values": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]},
        {"name": "diagnostico", "type": "choice",
         "values": ["Diabetes", "Hipertensión", "Infección respiratoria", "Fractura",
                     "Gastroenteritis", "Consulta general", "Alergia"]},
        {"name": "fecha_consulta", "type": "date", "start": "2024-01-01", "end": "2025-06-01"},
        {"name": "costo", "type": "float", "min": 500, "max": 50000, "mean": 3500, "std": 2000},
    ]
}

PROFILES = {
    "ventas": VENTAS_PROFILE,
    "rh": RH_PROFILE,
    "finanzas": FINANZAS_PROFILE,
    "salud": SALUD_PROFILE,
}
