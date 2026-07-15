from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Elemento, Pavimento


class GrupoDuplicarTests(TestCase):
    def setUp(self):
        self.pavimento = Pavimento.objects.create(nome='Terreo')
        self.base_1 = Elemento.objects.create(
            pavimento=self.pavimento,
            categoria=Elemento.CATEGORIA_ACO,
            tipo=Elemento.TIPO_PILAR,
            nome='P12',
            identificador='1',
            qtde=2,
            diametro=Decimal('10.0'),
            comprimento=Decimal('3.50'),
            peso_linear=Decimal('0.617'),
        )
        self.base_2 = Elemento.objects.create(
            pavimento=self.pavimento,
            categoria=Elemento.CATEGORIA_ACO,
            tipo=Elemento.TIPO_PILAR,
            nome='P12',
            identificador='2',
            qtde=4,
            diametro=Decimal('8.0'),
            comprimento=Decimal('2.75'),
            peso_linear=Decimal('0.395'),
        )

    def post_duplicar(self, nomes):
        return self.client.post(reverse('core:grupo_duplicar', args=[self.pavimento.pk]), {
            'categoria': Elemento.CATEGORIA_ACO,
            'tipo': Elemento.TIPO_PILAR,
            'nome': 'P12',
            'novo_nome': nomes,
        })

    def test_duplica_grupo_para_varios_nomes(self):
        response = self.post_duplicar('P1, P2, P3')

        self.assertRedirects(response, reverse('core:pavimento_detail', args=[self.pavimento.pk]))
        for nome in ['P1', 'P2', 'P3']:
            clones = Elemento.objects.filter(
                pavimento=self.pavimento,
                categoria=Elemento.CATEGORIA_ACO,
                tipo=Elemento.TIPO_PILAR,
                nome=nome,
            ).order_by('identificador')
            self.assertEqual(clones.count(), 2)
            self.assertEqual(clones[0].identificador, self.base_1.identificador)
            self.assertEqual(clones[0].qtde, self.base_1.qtde)
            self.assertEqual(clones[0].diametro, self.base_1.diametro)
            self.assertEqual(clones[0].comprimento, self.base_1.comprimento)
            self.assertEqual(clones[0].peso_linear, self.base_1.peso_linear)
            self.assertEqual(clones[1].identificador, self.base_2.identificador)

    def test_ignora_nomes_vazios_e_repetidos(self):
        self.post_duplicar('P1, , P1; P2\nP2')

        self.assertEqual(Elemento.objects.filter(nome='P1').count(), 2)
        self.assertEqual(Elemento.objects.filter(nome='P2').count(), 2)
        self.assertEqual(Elemento.objects.exclude(nome='P12').count(), 4)


class ElementoConcretoTests(TestCase):
    def test_calcula_volume_do_concreto_automaticamente(self):
        pavimento = Pavimento.objects.create(nome='Terreo')

        elemento = Elemento.objects.create(
            pavimento=pavimento,
            categoria=Elemento.CATEGORIA_CONCRETO,
            tipo=Elemento.TIPO_PILAR,
            nome='P1',
            medida_1=Decimal('0.20'),
            medida_2=Decimal('0.30'),
            comprimento=Decimal('3.00'),
            identificador='1',
            qtde=5,
        )

        self.assertEqual(elemento.volume, Decimal('0.180'))
        self.assertEqual(elemento.identificador, '')
        self.assertEqual(elemento.qtde, 1)
        self.assertIsNone(elemento.diametro)
        self.assertIsNone(elemento.peso_linear)


class ElementoInlineEditTests(TestCase):
    def test_edita_elemento_com_formulario_prefixado(self):
        pavimento = Pavimento.objects.create(nome='Terreo')
        elemento = Elemento.objects.create(
            pavimento=pavimento,
            categoria=Elemento.CATEGORIA_ACO,
            tipo=Elemento.TIPO_PILAR,
            nome='P1',
            identificador='1',
            qtde=2,
            diametro=Decimal('10.0'),
            comprimento=Decimal('3.50'),
            peso_linear=Decimal('0.617'),
        )
        prefix = f'edit-{elemento.pk}'

        response = self.client.post(
            reverse('core:elemento_edit', args=[pavimento.pk, elemento.pk]),
            {
                f'{prefix}-categoria': Elemento.CATEGORIA_ACO,
                f'{prefix}-tipo': Elemento.TIPO_PILAR,
                f'{prefix}-nome': 'P2',
                f'{prefix}-identificador': '3',
                f'{prefix}-qtde': '5',
                f'{prefix}-diametro': '8.0',
                f'{prefix}-comprimento': '2.40',
                f'{prefix}-peso_linear': '0.395',
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("core:pavimento_detail", args=[pavimento.pk])}#elemento-{elemento.pk}',
            fetch_redirect_response=False,
        )
        elemento.refresh_from_db()
        self.assertEqual(elemento.nome, 'P2')
        self.assertEqual(elemento.identificador, '3')
        self.assertEqual(elemento.qtde, 5)
        self.assertEqual(elemento.diametro, Decimal('8.0'))


class RelatorioResumoAcoTests(TestCase):
    def test_exporta_resumo_de_aco_em_pdf(self):
        terreo = Pavimento.objects.create(nome='Terreo')
        superior = Pavimento.objects.create(nome='Superior')

        Elemento.objects.create(
            pavimento=terreo,
            categoria=Elemento.CATEGORIA_ACO,
            tipo=Elemento.TIPO_PILAR,
            nome='P1',
            identificador='1',
            qtde=2,
            diametro=Decimal('10.0'),
            comprimento=Decimal('3.00'),
            peso_linear=Decimal('1.000'),
        )
        Elemento.objects.create(
            pavimento=terreo,
            categoria=Elemento.CATEGORIA_ACO,
            tipo=Elemento.TIPO_VIGA,
            nome='V1',
            identificador='1',
            qtde=1,
            diametro=Decimal('10.0'),
            comprimento=Decimal('4.00'),
            peso_linear=Decimal('2.000'),
        )
        forma = Elemento.objects.create(
            pavimento=terreo,
            categoria=Elemento.CATEGORIA_FORMA,
            tipo=Elemento.TIPO_VIGA,
            nome='V1',
            medida='2.00',
            comprimento=Decimal('5.00'),
        )
        concreto = Elemento.objects.create(
            pavimento=terreo,
            categoria=Elemento.CATEGORIA_CONCRETO,
            tipo=Elemento.TIPO_PILAR,
            nome='P1',
            medida_1=Decimal('0.20'),
            medida_2=Decimal('0.30'),
            comprimento=Decimal('3.00'),
        )
        Elemento.objects.filter(pk=forma.pk).update(peso_total=Decimal('999.00'))
        Elemento.objects.filter(pk=concreto.pk).update(peso_total=Decimal('777.00'))
        Elemento.objects.create(
            pavimento=superior,
            categoria=Elemento.CATEGORIA_ACO,
            tipo=Elemento.TIPO_SAPATA,
            nome='S1',
            identificador='1',
            qtde=5,
            diametro=Decimal('8.0'),
            comprimento=Decimal('1.00'),
            peso_linear=Decimal('1.000'),
        )

        response = self.client.get(reverse('core:relatorio_resumo_aco'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('filename="relatorio-resumo-aco.pdf"', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn(b'Resumo sintetico', response.content)
        self.assertIn(b'Total geral', response.content)
        self.assertNotIn(b'999,00', response.content)
        self.assertNotIn(b'777,00', response.content)
