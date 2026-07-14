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
            'medida',
            'identificador',
            'qtde',
            'diametro',
            'comprimento',
            'peso_linear',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome_campo in ['tipo', 'identificador', 'qtde']:
            self.fields[nome_campo].required = False
            self.fields[nome_campo].widget.attrs['data-campo-generico'] = '1'
        self.fields['medida'].required = False
        self.fields['medida'].widget.attrs['data-campo-forma'] = '1'
        for nome_campo in ['diametro', 'comprimento', 'peso_linear']:
            self.fields[nome_campo].required = False
            self.fields[nome_campo].widget.attrs['data-campo-aco'] = '1'
        self.fields['comprimento'].widget.attrs['data-campo-forma'] = '1'

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')
        campos_genericos = ['tipo', 'identificador', 'qtde']
        campos_aco = ['diametro', 'comprimento', 'peso_linear']

        if categoria == Elemento.CATEGORIA_ACO:
            for nome_campo in campos_genericos:
                if cleaned_data.get(nome_campo) in [None, '']:
                    self.add_error(nome_campo, 'Este campo e obrigatorio para Aco.')
            for nome_campo in campos_aco:
                if cleaned_data.get(nome_campo) in [None, '']:
                    self.add_error(nome_campo, 'Este campo e obrigatorio para Aco.')
            cleaned_data['medida'] = ''
        elif categoria == Elemento.CATEGORIA_FORMA:
            if cleaned_data.get('medida') in [None, '']:
                self.add_error('medida', 'Este campo e obrigatorio para Forma.')
            if cleaned_data.get('comprimento') in [None, '']:
                self.add_error('comprimento', 'Este campo e obrigatorio para Forma.')
            cleaned_data['tipo'] = ''
            cleaned_data['identificador'] = ''
            cleaned_data['qtde'] = 1
            cleaned_data['diametro'] = None
            cleaned_data['peso_linear'] = None
        else:
            for nome_campo in campos_genericos:
                if cleaned_data.get(nome_campo) in [None, '']:
                    self.add_error(nome_campo, 'Este campo e obrigatorio para Concreto.')
            cleaned_data['medida'] = ''
            for nome_campo in campos_aco:
                cleaned_data[nome_campo] = None

        return cleaned_data
