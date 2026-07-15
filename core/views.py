import re
from decimal import Decimal
from io import BytesIO
from itertools import groupby

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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


def formatar_decimal_br(valor):
    if valor is None:
        return ''
    return f'{valor:.2f}'.replace('.', ',')


def pavimentos_filtrados(busca=''):
    pavimentos = Pavimento.objects.prefetch_related('elementos').all()
    if busca:
        pavimentos = pavimentos.filter(nome__icontains=busca)
    return sorted(pavimentos, key=lambda p: chave_natural(p.nome))


def resumo_aco_por_pavimentos(pavimentos):
    """Resume somente o peso de aco, separado por pavimento e tipo."""
    tipos = [{'codigo': codigo, 'rotulo': rotulo} for codigo, rotulo in Elemento.TIPO_CHOICES]
    totais_por_tipo = {tipo['codigo']: Decimal('0') for tipo in tipos}
    linhas = []
    total_geral = Decimal('0')

    for pavimento in pavimentos:
        elementos_aco = [e for e in pavimento.elementos.all() if e.eh_aco]
        total_pavimento = Decimal('0')
        totais_tipo = []

        for tipo in tipos:
            subtotal = sum(
                (e.peso_total for e in elementos_aco if e.tipo == tipo['codigo']),
                Decimal('0'),
            )
            totais_tipo.append({
                'codigo': tipo['codigo'],
                'rotulo': tipo['rotulo'],
                'peso_total': subtotal,
            })
            totais_por_tipo[tipo['codigo']] += subtotal
            total_pavimento += subtotal

        linhas.append({
            'pavimento': pavimento,
            'tipos': totais_tipo,
            'total': total_pavimento,
        })
        total_geral += total_pavimento

    return {
        'tipos': tipos,
        'linhas': linhas,
        'totais_tipos': [
            {
                'codigo': tipo['codigo'],
                'rotulo': tipo['rotulo'],
                'peso_total': totais_por_tipo[tipo['codigo']],
            }
            for tipo in tipos
        ],
        'total_geral': total_geral,
    }


def elementos_aco_do_pavimento(pavimento):
    return sorted(
        [e for e in pavimento.elementos.all() if e.eh_aco],
        key=lambda e: (e.tipo, chave_natural(e.nome), chave_natural(e.identificador)),
    )


def criar_documento_pdf(buffer):
    return SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24,
        pageCompression=0,
    )


def estilo_tabela_pdf(linha_total=True):
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d5d8dc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f9fb')]),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]
    if linha_total:
        estilo.extend([
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eaf2f8')),
        ])
    return TableStyle(estilo)


def tabela_resumo_aco_pdf(resumo_aco):
    dados = [[
        'Pavimento',
        *[f'{tipo["rotulo"]} (kg)' for tipo in resumo_aco['tipos']],
        'Total aco (kg)',
    ]]
    for linha in resumo_aco['linhas']:
        dados.append([
            linha['pavimento'].nome,
            *[formatar_decimal_br(tipo['peso_total']) for tipo in linha['tipos']],
            formatar_decimal_br(linha['total']),
        ])
    dados.append([
        'Total geral',
        *[formatar_decimal_br(tipo['peso_total']) for tipo in resumo_aco['totais_tipos']],
        formatar_decimal_br(resumo_aco['total_geral']),
    ])

    tabela = Table(dados, repeatRows=1)
    tabela.setStyle(estilo_tabela_pdf())
    tabela.setStyle(TableStyle([('ALIGN', (1, 1), (-1, -1), 'RIGHT')]))
    return tabela


def tabela_elementos_aco_pdf(elementos_aco, total_pavimento):
    dados = [[
        'Tipo',
        'Nome',
        'ID',
        'QTDE',
        'DIAM (mm)',
        'L (m)',
        'Peso linear',
        'Peso unit. PC',
        'Peso total',
    ]]
    linhas_grupo = []
    for (tipo, nome), itens in groupby(elementos_aco, key=lambda e: (e.tipo_rotulo, e.nome)):
        itens = list(itens)
        total_grupo = sum((e.peso_total for e in itens), Decimal('0'))
        quantidade_itens = len(itens)
        rotulo_item = 'item' if quantidade_itens == 1 else 'itens'
        linhas_grupo.append(len(dados))
        dados.append([
            f'{tipo} {nome} - {quantidade_itens} {rotulo_item} - Total: {formatar_decimal_br(total_grupo)} kg',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
        ])
        for elemento in itens:
            dados.append([
                elemento.tipo_rotulo,
                elemento.nome,
                elemento.identificador,
                elemento.qtde,
                elemento.get_diametro_display(),
                formatar_decimal_br(elemento.comprimento),
                formatar_decimal_br(elemento.peso_linear),
                formatar_decimal_br(elemento.peso_unitario),
                formatar_decimal_br(elemento.peso_total),
            ])
    dados.append(['Total do pavimento', '', '', '', '', '', '', '', formatar_decimal_br(total_pavimento)])

    tabela = Table(
        dados,
        repeatRows=1,
        colWidths=[70, 90, 50, 42, 58, 55, 75, 80, 75],
    )
    estilo = [
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('SPAN', (0, -1), (7, -1)),
    ]
    for linha in linhas_grupo:
        estilo.extend([
            ('SPAN', (0, linha), (-1, linha)),
            ('BACKGROUND', (0, linha), (-1, linha), colors.HexColor('#d6e4f0')),
            ('TEXTCOLOR', (0, linha), (-1, linha), colors.HexColor('#1a5276')),
            ('FONTNAME', (0, linha), (-1, linha), 'Helvetica-Bold'),
            ('ALIGN', (0, linha), (-1, linha), 'LEFT'),
        ])

    tabela.setStyle(estilo_tabela_pdf())
    tabela.setStyle(TableStyle(estilo))
    return tabela


def elemento_form_prefix(elemento):
    return f'edit-{elemento.pk}'


def redirect_pavimento_detail(pavimento, anchor=''):
    url = reverse('core:pavimento_detail', kwargs={'pk': pavimento.pk})
    if anchor:
        url = f'{url}#{anchor}'
    return redirect(url)


def contexto_pavimento_detail(
    pavimento,
    form,
    duplicando=None,
    preenchido_automatico=False,
    formulario_edicao=None,
    elemento_editando_pk=None,
):
    elementos = sorted(
        pavimento.elementos.all(),
        key=lambda e: (e.categoria, e.tipo, chave_natural(e.nome), chave_natural(e.identificador)),
    )

    return {
        'pavimento': pavimento,
        'grupos': agrupar_elementos(elementos),
        'resumo_diametros': resumo_por_diametro(elementos),
        'tem_elementos': bool(elementos),
        'form': form,
        'nomes_forma_por_tipo': form.nomes_forma_por_tipo,
        'duplicando': duplicando,
        'preenchido_automatico': preenchido_automatico,
        'elemento_editando_pk': elemento_editando_pk,
        'formulario_edicao': formulario_edicao,
    }


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
                    'area_total': sum(e.area for e in itens),
                    'volume_total': sum(e.volume for e in itens),
                    'eh_aco': eh_aco,
                    'eh_forma': eh_forma,
                })
            tipos.append({
                'tipo': tipo,
                'nomes': nomes,
                'peso_total': sum(n['peso_total'] for n in nomes),
                'area_total': sum(n['area_total'] for n in nomes),
                'volume_total': sum(n['volume_total'] for n in nomes),
            })
        grupos.append({
            'categoria': categoria,
            'eh_aco': itens_categoria[0].eh_aco,
            'eh_forma': itens_categoria[0].eh_forma,
            'eh_concreto': itens_categoria[0].eh_concreto,
            'tipos': tipos,
            'peso_total': sum(t['peso_total'] for t in tipos),
            'area_total': sum(t['area_total'] for t in tipos),
            'volume_total': sum(t['volume_total'] for t in tipos),
        })
    return grupos


def nomes_para_duplicar(valor):
    """Converte "P1, P2" ou nomes em linhas separadas em uma lista sem repeticao."""
    nomes = []
    vistos = set()
    for nome in re.split(r'[,;\r\n]+', valor or ''):
        nome = nome.strip()
        if nome and nome not in vistos:
            nomes.append(nome)
            vistos.add(nome)
    return nomes


def clonar_elemento(elemento, **alteracoes):
    campos = {
        'pavimento': elemento.pavimento,
        'categoria': elemento.categoria,
        'tipo': elemento.tipo,
        'nome': elemento.nome,
        'medida': elemento.medida,
        'medida_1': elemento.medida_1,
        'medida_2': elemento.medida_2,
        'identificador': elemento.identificador,
        'qtde': elemento.qtde,
        'diametro': elemento.diametro,
        'comprimento': elemento.comprimento,
        'peso_linear': elemento.peso_linear,
    }
    campos.update(alteracoes)
    return Elemento.objects.create(**campos)


def home(request):
    return redirect('core:pavimento_list')


def pavimento_list(request):
    busca = request.GET.get('q', '').strip()
    pavimentos = pavimentos_filtrados(busca)
    resumo_aco = resumo_aco_por_pavimentos(pavimentos)
    return render(request, 'core/pavimento_list.html', {
        'pavimentos': pavimentos,
        'busca': busca,
        'resumo_aco': resumo_aco,
    })


def relatorio_resumo_aco(request):
    busca = request.GET.get('q', '').strip()
    pavimentos = pavimentos_filtrados(busca)
    resumo_aco = resumo_aco_por_pavimentos(pavimentos)

    buffer = BytesIO()
    documento = criar_documento_pdf(buffer)
    estilos = getSampleStyleSheet()
    elementos = [
        Paragraph('Resumo sintetico', estilos['Title']),    
        Spacer(1, 14),
    ]
    elementos.append(tabela_resumo_aco_pdf(resumo_aco))
    elementos.extend([
        PageBreak(),
        Paragraph('Detalhamento por pavimento', estilos['Heading2']),
        Spacer(1, 8),
    ])

    for linha in resumo_aco['linhas']:
        pavimento = linha['pavimento']
        elementos_aco = elementos_aco_do_pavimento(pavimento)
        elementos.append(Paragraph(
            f'Pavimento: {pavimento.nome} - Total: {formatar_decimal_br(linha["total"])} kg',
            estilos['Heading3'],
        ))
        if elementos_aco:
            elementos.append(tabela_elementos_aco_pdf(elementos_aco, linha['total']))
        else:
            elementos.append(Paragraph('Nenhum elemento de aco cadastrado neste pavimento.', estilos['Normal']))
        elementos.append(Spacer(1, 14))

    documento.build(elementos)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio-resumo-aco.pdf"'
    return response


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
    formulario_edicao = None
    elemento_editando_pk = None
    if request.method == 'POST':
        form = ElementoForm(request.POST, pavimento=pavimento)
        if form.is_valid():
            elemento = form.save(commit=False)
            elemento.pavimento = pavimento
            elemento.save()
            messages.success(request, 'Elemento adicionado com sucesso.')
            return redirect_pavimento_detail(pavimento)
    else:
        duplicar_pk = request.GET.get('duplicar')
        if duplicar_pk:
            duplicando = pavimento.elementos.filter(pk=duplicar_pk).first()
        editar_pk = request.GET.get('editar')
        if editar_pk:
            elemento_editando = pavimento.elementos.filter(pk=editar_pk).first()
            if elemento_editando:
                elemento_editando_pk = elemento_editando.pk
                formulario_edicao = ElementoForm(
                    instance=elemento_editando,
                    pavimento=pavimento,
                    prefix=elemento_form_prefix(elemento_editando),
                )
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
                'medida_1': base.medida_1,
                'medida_2': base.medida_2,
                'identificador': base.identificador,
                'qtde': base.qtde,
                'diametro': base.diametro,
                'comprimento': base.comprimento,
                'peso_linear': base.peso_linear,
            }, pavimento=pavimento)
        else:
            form = ElementoForm(pavimento=pavimento)
    return render(
        request,
        'core/pavimento_detail.html',
        contexto_pavimento_detail(
            pavimento,
            form,
            duplicando,
            preenchido_automatico,
            formulario_edicao=formulario_edicao,
            elemento_editando_pk=elemento_editando_pk,
        ),
    )


def pavimento_delete(request, pk):
    pavimento = get_object_or_404(Pavimento, pk=pk)
    if request.method == 'POST':
        nome = pavimento.nome
        pavimento.delete()
        messages.success(request, f'Pavimento "{nome}" excluido.')
        return redirect('core:pavimento_list')
    return render(request, 'core/pavimento_confirm_delete.html', {'pavimento': pavimento})


def grupo_duplicar(request, pk):
    """Duplica todas as pecas de uma categoria+tipo+nome para um ou mais nomes."""
    pavimento = get_object_or_404(Pavimento, pk=pk)
    if request.method == 'POST':
        categoria = request.POST.get('categoria', Elemento.CATEGORIA_ACO)
        tipo = request.POST.get('tipo', '')
        nome = request.POST.get('nome', '')
        novos_nomes = nomes_para_duplicar(request.POST.get('novo_nome'))
        elementos = list(pavimento.elementos.filter(categoria=categoria, tipo=tipo, nome=nome))
        if not novos_nomes:
            messages.error(request, 'Informe ao menos um nome para duplicar o grupo.')
        elif not elementos:
            messages.error(request, 'Nenhuma peca encontrada para duplicar.')
        else:
            for novo_nome in novos_nomes:
                for elemento in elementos:
                    clonar_elemento(elemento, nome=novo_nome)
            total = len(elementos) * len(novos_nomes)
            nomes_texto = ', '.join(novos_nomes)
            messages.success(
                request,
                f'{total} peca(s) de "{nome}" duplicada(s) como "{nomes_texto}".'
            )
    return redirect_pavimento_detail(pavimento)


def elemento_delete(request, pk, elemento_pk):
    pavimento = get_object_or_404(Pavimento, pk=pk)
    elemento = get_object_or_404(pavimento.elementos, pk=elemento_pk)
    if request.method == 'POST':
        elemento.delete()
        messages.success(request, 'Elemento excluido.')
    return redirect_pavimento_detail(pavimento)


def elemento_edit(request, pk, elemento_pk):
    pavimento = get_object_or_404(Pavimento, pk=pk)
    elemento = get_object_or_404(pavimento.elementos, pk=elemento_pk)
    prefix = elemento_form_prefix(elemento)
    if request.method == 'POST':
        post_prefix = prefix if f'{prefix}-categoria' in request.POST else None
        form = ElementoForm(request.POST, instance=elemento, pavimento=pavimento, prefix=post_prefix)
        if form.is_valid():
            form.save()
            messages.success(request, 'Elemento atualizado com sucesso.')
            return redirect_pavimento_detail(pavimento, f'elemento-{elemento.pk}')

        form_adicionar = ElementoForm(pavimento=pavimento)
        return render(
            request,
            'core/pavimento_detail.html',
            contexto_pavimento_detail(
                pavimento,
                form_adicionar,
                formulario_edicao=form,
                elemento_editando_pk=elemento.pk,
            ),
        )
    else:
        form = ElementoForm(instance=elemento, pavimento=pavimento)
    return render(request, 'core/elemento_form.html', {
        'pavimento': pavimento,
        'elemento': elemento,
        'form': form,
        'nomes_forma_por_tipo': form.nomes_forma_por_tipo,
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
