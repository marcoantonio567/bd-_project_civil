import re
from decimal import Decimal, InvalidOperation

from django import forms

from .models import Elemento, Pavimento


def chave_natural(texto):
    return [int(parte) if parte.isdigit() else parte.lower()
            for parte in re.split(r'(\d+)', texto)]


class PavimentoForm(forms.ModelForm):
    class Meta:
        model = Pavimento
        fields = ['nome']


class ElementoForm(forms.ModelForm):
    class Meta:
        model = Elemento
        fields = [
            'categoria',
            'tipo',
            'nome',
            'medida',
            'medida_1',
            'medida_2',
            'identificador',
            'qtde',
            'diametro',
            'comprimento',
            'peso_linear',
        ]

    def __init__(self, *args, pavimento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pavimento = pavimento or getattr(self.instance, 'pavimento', None)
        self.nomes_forma_por_tipo = self._nomes_forma_por_tipo()

        self.fields['tipo'].required = False
        self.fields['tipo'].widget.attrs['data-campo-tipo'] = '1'
        for nome_campo in ['identificador', 'qtde']:
            self.fields[nome_campo].required = False
            self.fields[nome_campo].widget.attrs['data-campo-generico'] = '1'
        self.fields['medida'].required = False
        self.fields['medida'].widget.attrs['data-campo-forma'] = '1'
        for nome_campo in ['medida_1', 'medida_2']:
            self.fields[nome_campo].required = False
            self.fields[nome_campo].widget.attrs['data-campo-concreto'] = '1'
        for nome_campo in ['diametro', 'comprimento', 'peso_linear']:
            self.fields[nome_campo].required = False
            self.fields[nome_campo].widget.attrs['data-campo-aco'] = '1'
        self.fields['comprimento'].widget.attrs['data-campo-forma'] = '1'
        self.fields['comprimento'].widget.attrs['data-campo-concreto'] = '1'

    def _nomes_forma_por_tipo(self):
        if not self.pavimento:
            return {}

        nomes = set(
            self.pavimento.elementos
            .exclude(nome='')
            .values_list('nome', flat=True)
        )

        if self.instance.pk and self.instance.eh_forma:
            nomes.add(self.instance.nome)

        nomes_ordenados = sorted(nomes, key=chave_natural)
        return {tipo: nomes_ordenados for tipo, _rotulo in Elemento.TIPO_CHOICES}

    def _medida_decimal(self, valor):
        try:
            medida = Decimal(str(valor).strip().replace(',', '.'))
        except (InvalidOperation, AttributeError):
            return None
        if medida <= 0:
            return None
        return medida

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')
        campos_aco = ['diametro', 'comprimento', 'peso_linear']

        if categoria == Elemento.CATEGORIA_ACO:
            for nome_campo in ['tipo', 'identificador', 'qtde']:
                if cleaned_data.get(nome_campo) in [None, '']:
                    self.add_error(nome_campo, 'Este campo e obrigatorio para Aco.')
            for nome_campo in campos_aco:
                if cleaned_data.get(nome_campo) in [None, '']:
                    self.add_error(nome_campo, 'Este campo e obrigatorio para Aco.')
            cleaned_data['medida'] = ''
        elif categoria == Elemento.CATEGORIA_FORMA:
            tipo = cleaned_data.get('tipo')
            nome = cleaned_data.get('nome')
            medida = self._medida_decimal(cleaned_data.get('medida'))

            if not tipo:
                self.add_error('tipo', 'Este campo e obrigatorio para Forma.')
            if not nome:
                self.add_error('nome', 'Selecione um nome para Forma.')
            if medida is None:
                self.add_error('medida', 'Informe uma medida numerica maior que zero.')
            else:
                cleaned_data['medida'] = str(medida)
            cleaned_data['medida_1'] = None
            cleaned_data['medida_2'] = None
            if cleaned_data.get('comprimento') in [None, ''] or cleaned_data.get('comprimento') <= 0:
                self.add_error('comprimento', 'Informe um comprimento maior que zero.')

            if tipo and nome:
                nomes_disponiveis = self.nomes_forma_por_tipo.get(tipo, [])
                if nome not in nomes_disponiveis:
                    self.add_error('nome', 'Selecione um nome cadastrado no pavimento.')

            cleaned_data['identificador'] = ''
            cleaned_data['qtde'] = 1
            cleaned_data['diametro'] = None
            cleaned_data['peso_linear'] = None
        else:
            for nome_campo in ['tipo']:
                if cleaned_data.get(nome_campo) in [None, '']:
                    self.add_error(nome_campo, 'Este campo e obrigatorio para Concreto.')
            for nome_campo in ['medida_1', 'medida_2', 'comprimento']:
                if cleaned_data.get(nome_campo) in [None, ''] or cleaned_data.get(nome_campo) <= 0:
                    self.add_error(nome_campo, 'Informe uma medida maior que zero.')
            cleaned_data['medida'] = ''
            cleaned_data['identificador'] = ''
            cleaned_data['qtde'] = 1
            for nome_campo in ['diametro', 'peso_linear']:
                cleaned_data[nome_campo] = None

        return cleaned_data
