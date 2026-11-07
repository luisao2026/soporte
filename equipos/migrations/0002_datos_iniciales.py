from django.db import migrations

CATEGORIAS = [
    "Tablet",
    "Laptop",
    "Computadora portátil",
    "Dispositivo móvil",
    "Proyector",
    "Computadora de escritorio",
]

MARCAS = {
    "HP": ["ProBook 450 G8", "EliteDesk 800 G6", "Pavilion 15"],
    "Dell": ["Latitude 5420", "OptiPlex 7090", "Inspiron 15 3511"],
    "Lenovo": ["ThinkPad E14", "IdeaPad 3", "ThinkCentre M70q", "Tab M10"],
    "Asus": ["VivoBook 15", "ExpertBook B1"],
    "Acer": ["Aspire 5", "Veriton X"],
}


def cargar(apps, schema_editor):
    Categoria = apps.get_model("equipos", "Categoria")
    Marca = apps.get_model("equipos", "Marca")
    Modelo = apps.get_model("equipos", "Modelo")
    for nombre in CATEGORIAS:
        Categoria.objects.get_or_create(nombre=nombre)
    for marca, modelos in MARCAS.items():
        m, _ = Marca.objects.get_or_create(nombre=marca)
        for nombre in modelos:
            Modelo.objects.get_or_create(marca=m, nombre=nombre)


class Migration(migrations.Migration):
    dependencies = [("equipos", "0001_initial")]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
