from decimal import Decimal

from django.db import models


class Pavimento(models.Model):
    nome = models.CharField('Nome', max_length=100, unique=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Pavimento'
        verbose_name_plural = 'Pavimentos'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def peso_total_geral(self):
        return sum((e.peso_total for e in self.elementos.all()), Decimal('0'))


class Elemento(models.Model):
    CATEGORIA_ACO = 'aco'
    CATEGORIA_FORMA = 'forma'
    CATEGORIA_CONCRETO = 'concreto'
    CATEGORIA_CHOICES = [
        (CATEGORIA_ACO, 'Aço'),
        (CATEGORIA_FORMA, 'Forma'),
        (CATEGORIA_CONCRETO, 'Concreto'),
    ]

    TIPO_PILAR = 'pilar'
    TIPO_SAPATA = 'sapata'
    TIPO_VIGA = 'viga'
    TIPO_ESTACA = 'estaca'
    TIPO_LAJE = 'laje'
    TIPO_CHOICES = [
        (TIPO_PILAR, 'Pilar'),
        (TIPO_SAPATA, 'Sapata'),
        (TIPO_VIGA, 'Viga'),
        (TIPO_ESTACA, 'Estaca'),
        (TIPO_LAJE, 'Laje'),
    ]

    DIAMETRO_CHOICES = [
        (Decimal('5.0'), '5,0'),
        (Decimal('6.3'), '6,3'),
        (Decimal('8.0'), '8,0'),
        (Decimal('10.0'), '10'),
        (Decimal('12.5'), '12,5'),
        (Decimal('16.0'), '16'),
        (Decimal('20.0'), '20'),
    ]

    pavimento = models.ForeignKey(
        Pavimento,
        on_delete=models.CASCADE,
        related_name='elementos',
        verbose_name='Pavimento',
    )
    categoria = models.CharField(
        'Elemento',
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default=CATEGORIA_ACO,
    )
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES)
    nome = models.CharField('Nome do tipo', max_length=100)
    identificador = models.CharField('ID', max_length=50)
    qtde = models.PositiveIntegerField('QTDE')
    diametro = models.DecimalField(
        'DIAM (mm)',
        max_digits=5,
        decimal_places=1,
        choices=DIAMETRO_CHOICES,
        null=True,
        blank=True,
    )
    comprimento = models.DecimalField('L (m)', max_digits=8, decimal_places=2, null=True, blank=True)
    peso_linear = models.DecimalField('Peso linear (kg/m)', max_digits=8, decimal_places=3, null=True, blank=True)
    peso_total = models.DecimalField(
        'Peso total (kg)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        editable=False,
    )
    peso_unitario = models.DecimalField(
        'Peso unit. PC (kg)',
        max_digits=12,
        decimal_places=3,
        default=Decimal('0'),
        editable=False,
    )

    class Meta:
        verbose_name = 'Elemento'
        verbose_name_plural = 'Elementos'
        ordering = ['categoria', 'tipo', 'nome', 'identificador']

    def __str__(self):
        return f'{self.get_categoria_display()} - {self.get_tipo_display()} {self.nome} ({self.identificador})'

    @property
    def eh_aco(self):
        return self.categoria == self.CATEGORIA_ACO

    def save(self, *args, **kwargs):
        if self.eh_aco and self.comprimento is not None and self.peso_linear is not None:
            self.peso_unitario = self.comprimento * self.peso_linear
            self.peso_total = self.qtde * self.peso_unitario
        else:
            self.diametro = None
            self.comprimento = None
            self.peso_linear = None
            self.peso_unitario = Decimal('0')
            self.peso_total = Decimal('0')
        super().save(*args, **kwargs)
