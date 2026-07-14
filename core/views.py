import re
from itertools import groupby

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ElementoForm, PavimentoForm
from .models import Elemento, Pavimento


def chave_natural(texto):
    """Ordena letras alfabeticamente e numeros numericamente (P1, P2, P10)."""
    return [int(parte) if parte.isdigit() else parte.lower()
            for parte in re.split(r'(\d+)', texto)]


def resumo_por_diametro(elementos):
    """Agrupa elementos de aco por diametro e soma cada bitola."""
    resumo = []
    elementos_aco = [e for e in elementos if e.eh_aco and e.diametro is not None]
    ordenados = sorted(elementos_aco, key=lambda e: e.diametro)
    for diametro, itens in groupby(ordenados, key=lambda e: e.diametro):
        itens = list(itens)
        resumo.append({
            'rotulo': itens[0].get_diametro_display(),
            'qtde': sum(e.qtde for e in itens),
            'comprimento': sum(e.qtde * e.comprimento for e in itens),
            'peso_total': sum(e.peso_total for e in itens),
        })
    return resumo


def agrupar_elementos(elementos):
    """Agrupa elementos por categoria, tipo e nome, com subtotais."""
    grupos = []
    for categoria, itens_categoria in groupby(elementos, key=lambda e: e.get_categoria_display()):
        itens_categoria = list(itens_categoria)
        tipos = []
        for tipo, itens_tipo in groupby(itens_categoria, key=lambda e: e.tipo_rotulo):
            nomes = []
            for nome, itens in groupby(itens_tipo, key=lambda e: e.nome):
                itens = list(itens)
                eh_aco = itens[0].eh_aco
                eh_forma = itens[0].eh_forma
                nomes.append({
                    'nome': nome,
                    'elementos': itens,
                    'qtde': sum(e.qtde for e in itens),
                    'diametros': resumo_por_diametro(itens) if eh_aco else [],
                    'peso_total': sum(e.peso_total for e in itens),
                    'eh_aco': eh_aco,
                    'eh_forma': eh_forma,
                })
            tipos.append({
                'tipo': tipo,
                'nomes': nomes,
                'peso_total': sum(n['peso_total'] for n in nomes),
            })
        grupos.append({
            'categoria': categoria,
            'eh_aco': itens_categoria[0].eh_aco,
            'eh_forma': itens_categoria[0].eh_forma,
            'tipos': tipos,
            'peso_total': sum(t['peso_total'] for t in tipos),
        })
    return grupos


def home(request):
    return redirect('core:pavimento_list')


def pavimento_list(request):
    busca = request.GET.get('q', '').strip()
    pavimentos = Pavimento.objects.all()
    if busca:
        pavimentos = pavimentos.filter(nome__icontains=busca)
    pavimentos = sorted(pavimentos, key=lambda p: chave_natural(p.nome))
    return render(request, 'core/pavimento_list.html', {
        'pavimentos': pavimentos,
        'busca': busca,
    })


def pavimento_create(request):
    if request.method == 'POST':
        form = PavimentoForm(request.POST)
        if form.is_valid():
            pavimento = form.save()
            messages.success(request, f'Pavimento "{pavimento.nome}" cadastrado com sucesso.')
            return redirect('core:pavimento_detail', pk=pavimento.pk)
    else:
        form = PavimentoForm()
    return render(request, 'core/pavimento_form.html', {'form': form})


def pavimento_detail(request, pk):
    pavimento = get_object_or_404(Pavimento, pk=pk)
    duplicando = None
    preenchido_automatico = False
    if request.method == 'POST':
        form = ElementoForm(request.POST)
        if form.is_valid():
            elemento = form.save(commit=False)
            elemento.pavimento = pavimento
            elemento.save()
            messages.success(request, 'Elemento adicionado com sucesso.')
            return redirect('core:pavimento_detail', pk=pavimento.pk)
    else:
        duplicar_pk = request.GET.get('duplicar')
        if duplicar_pk:
            duplicando = pavimento.elementos.filter(pk=duplicar_pk).first()
        base = duplicando
        if not base and not request.GET.get('novo'):
            base = pavimento.elementos.order_by('-pk').first()
            preenchido_automatico = base is not None
        if base:
            form = ElementoForm(initial={
                'categoria': base.categoria,
                'tipo': base.tipo,
                'nome': base.nome,
                'medida': base.medida,
                'identificador': base.identificador,
                'qtde': base.qtde,
                'diametro': base.diametro,
                'comprimento': base.comprimento,
                'peso_linear': base.peso_linear,
            })
        else:
            form = ElementoForm()
    elementos = sorted(
        pavimento.elementos.all(),
        key=lambda e: (e.categoria, e.tipo, chave_natural(e.nome), chave_natural(e.identificador)),
    )
    return render(request, 'core/pavimento_detail.html', {
        'pavimento': pavimento,
        'grupos': agrupar_elementos(elementos),
        'resumo_diametros': resumo_por_diametro(elementos),
        'tem_elementos': bool(elementos),
        'form': form,
        'duplicando': duplicando,
        'preenchido_automatico': preenchido_automatico,
    })


def pavimento_delete(request, pk):
    pavimento = get_object_or_404(Pavimento, pk=pk)
    if request.method == 'POST':
        nome = pavimento.nome
        pavimento.delete()
        messages.success(request, f'Pavimento "{nome}" excluido.')
        return redirect('core:pavimento_list')
    return render(request, 'core/pavimento_confirm_delete.html', {'pavimento': pavimento})


def grupo_duplicar(request, pk):
    """Duplica todas as pecas de uma categoria+tipo+nome com um novo nome."""
    pavimento = get_object_or_404(Pavimento, pk=pk)
    if request.method == 'POST':
        categoria = request.POST.get('categoria', Elemento.CATEGORIA_ACO)
        tipo = request.POST.get('tipo', '')
        nome = request.POST.get('nome', '')
        novo_nome = (request.POST.get('novo_nome') or '').strip()
        elementos = list(pavimento.elementos.filter(categoria=categoria, tipo=tipo, nome=nome))
        if not novo_nome:
            messages.error(request, 'Informe o novo nome para duplicar o grupo.')
        elif not elementos:
            messages.error(request, 'Nenhuma peca encontrada para duplicar.')
        else:
            for elemento in elementos:
                elemento.pk = None
                elemento.nome = novo_nome
                elemento.save()
            messages.success(
                request,
                f'{len(elementos)} peca(s) de "{nome}" duplicada(s) como "{novo_nome}".'
            )
    return redirect('core:pavimento_detail', pk=pavimento.pk)


def elemento_delete(request, pk, elemento_pk):
    pavimento = get_object_or_404(Pavimento, pk=pk)
    elemento = get_object_or_404(pavimento.elementos, pk=elemento_pk)
    if request.method == 'POST':
        elemento.delete()
        messages.success(request, 'Elemento excluido.')
    return redirect('core:pavimento_detail', pk=pavimento.pk)


def elemento_edit(request, pk, elemento_pk):
    pavimento = get_object_or_404(Pavimento, pk=pk)
    elemento = get_object_or_404(pavimento.elementos, pk=elemento_pk)
    if request.method == 'POST':
        form = ElementoForm(request.POST, instance=elemento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Elemento atualizado com sucesso.')
            return redirect('core:pavimento_detail', pk=pavimento.pk)
    else:
        form = ElementoForm(instance=elemento)
    return render(request, 'core/elemento_form.html', {
        'pavimento': pavimento,
        'elemento': elemento,
        'form': form,
    })


def pavimento_copiar(request, pk):
    """Copia pecas selecionadas de outro pavimento para este."""
    pavimento = get_object_or_404(Pavimento, pk=pk)
    outros_pavimentos = Pavimento.objects.exclude(pk=pk)
    outros_pavimentos = sorted(outros_pavimentos, key=lambda p: chave_natural(p.nome))

    origem_id = request.POST.get('origem') or request.GET.get('origem')
    origem = None
    grupos_origem = []
    if origem_id:
        origem = get_object_or_404(Pavimento, pk=origem_id)
        elementos_origem = sorted(
            origem.elementos.all(),
            key=lambda e: (e.categoria, e.tipo, chave_natural(e.nome), chave_natural(e.identificador)),
        )
        grupos_origem = agrupar_elementos(elementos_origem)

    if request.method == 'POST':
        if not origem:
            messages.error(request, 'Selecione o pavimento de origem.')
        else:
            ids = request.POST.getlist('elementos')
            elementos = list(origem.elementos.filter(pk__in=ids))
            if not elementos:
                messages.error(request, 'Selecione ao menos uma peca para copiar.')
            else:
                for elemento in elementos:
                    elemento.pk = None
                    elemento.pavimento = pavimento
                    elemento.save()
                messages.success(
                    request,
                    f'{len(elementos)} peca(s) copiada(s) de "{origem.nome}". '
                    f'Agora edite o que for necessario.'
                )
                return redirect('core:pavimento_detail', pk=pavimento.pk)

    return render(request, 'core/pavimento_copiar.html', {
        'pavimento': pavimento,
        'outros_pavimentos': outros_pavimentos,
        'origem': origem,
        'grupos_origem': grupos_origem,
    })
