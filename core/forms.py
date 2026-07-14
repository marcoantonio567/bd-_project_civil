from django import forms

from .models import Elemento, Pavimento


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
            'identificador',
            'qtde',
            'diametro',
            'comprimento',
            'peso_linear',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome_campo in ['diametro', 'comprimento', 'peso_linear']:
            self.fields[nome_campo].required = False
            self.fields[nome_campo].widget.attrs['data-campo-aco'] = '1'

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')
        campos_aco = ['diametro', 'comprimento', 'peso_linear']

        if categoria == Elemento.CATEGORIA_ACO:
            for nome_campo in campos_aco:
                if cleaned_data.get(nome_campo) in [None, '']:
                    self.add_error(nome_campo, 'Este campo é obrigatório para Aço.')
        else:
            for nome_campo in campos_aco:
                cleaned_data[nome_campo] = None

        return cleaned_data
