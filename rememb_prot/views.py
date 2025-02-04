from django.shortcuts import render ,redirect
from django.db.models import Q
from django.http import JsonResponse

from django.contrib import messages

import pandas as pd
import numpy as np
from scipy.stats import fisher_exact
import matplotlib.pyplot as plt

from io import BytesIO
import base64

from . models import Remembprot , Enrich , Dose , Cellmarker
from .utils import getbarplot
import json

def get_graph():
    buffer = BytesIO()
    plt.savefig(buffer, format = 'svg')
    buffer.seek(0)
    image_png = buffer.getvalue()
    graph = base64.b64encode(image_png)
    graph = graph.decode('utf-8')
    buffer.close()
    return graph


def home(request):
    protiens = Remembprot.objects.values('geneSymbol').distinct().count()
    trans_prot = Remembprot.objects.filter(isTrans = 'YES').count()
    context = {'protiens':protiens,'trans_prot':trans_prot}
    return render(request,'rememb_prot/home.html', context)

def browse(request):
    method = Remembprot.objects.values('protienExtractMethod').order_by('-protienExtractMethod').distinct()
    pmid = Remembprot.objects.values('pmid').distinct()
    cellortissue = Remembprot.objects.values('CellOrtissue').distinct()
    geneid = Remembprot.objects.values('geneID').distinct()
    context = {'pmid':pmid, 'method':method, 'cellortissue':cellortissue,
    'geneid': geneid}
    return render(request,'rememb_prot/browse.html', context)





def browseResult(request):
    method = request.POST.get("method")
    tissueCell = request.POST.get("tissueCell")
    species = request.POST.get("species")
    
    if tissueCell == None:
        results = Remembprot.objects.filter( Q(organism = species) & Q(protienExtractMethod = method )).values("pmid","geneSymbol","isTrans","profileOrDifex","contxtOfIdent")   
    else:
        results = Remembprot.objects.filter( Q(organism = species) & Q(protienExtractMethod = method  ) &
            Q(CellOrtissue = tissueCell) ).values("pmid","geneSymbol","isTrans","profileOrDifex","contxtOfIdent")
        

    df = pd.DataFrame(list(results))
    print(df)
    if df.empty:

        messages.error(request, 'could not find any result for your query.')
        return redirect('rememb_prot:browse')
    
    else:
        
        genes = df['geneSymbol'].tolist()   
        cmData = Cellmarker.objects.filter(Q(geneSymbol__in = genes) & Q(species = species) ).values()
        cmData = pd.DataFrame(list(cmData))
        
        if not cmData.empty:
            print(df.shape)
            df = df.merge(cmData, on = 'geneSymbol', how = 'left')
            print(df.shape)

        df.fillna('-', inplace=True)

        df.sort_values('isTrans', ascending = False, inplace=True)

        formatted_data = {}

        for _, row in df.iterrows():
            gene_symbol = row['geneSymbol']
            isTrans = row['isTrans']
            profileOrDifex = row['profileOrDifex']
            contxtOfIdent = row['contxtOfIdent']
            pmid = row['pmid']


            if gene_symbol not in formatted_data:
                gene_info = {
                    'gene': gene_symbol,
                    'Transmem_status': isTrans,
                    'profileOrDifferential' : profileOrDifex,
                    'contxtOfIdent' : contxtOfIdent,
                    'pmid' : pmid,
                    'cell marker status': []
                }
                if row['tissueType'] != '-' and row['cancerType'] != '-' and row['cellName'] != '-':

                    
                    cell_marker_info = {
                    'tissueType': row['tissueType'],
                    'cancerType': row['cancerType'],
                    'cellName': row['cellName']
                    }
                    gene_info['cell marker status'].append(cell_marker_info)
                else:
                    cell_marker_info = {
                    'tissueType': '-',
                    'cancerType': '-',
                    'cellName': '-'
                    }
                    gene_info['cell marker status'].append(cell_marker_info)


                formatted_data[gene_symbol] = gene_info

        
        
        final_formatted_data = list(formatted_data.values())

        print(final_formatted_data)


        context = { 'final_formatted_data':final_formatted_data, 'species':species , 'method':method, 'tissueCell':tissueCell }
 
        return render(request,'rememb_prot/browseresultnew.html',context)
        



def pvalue_calc(list_hit,pop_hit,list_total):
    pop_tot = 13651
    data = np.array([ [list_hit,pop_hit-list_hit],[list_total-list_hit, pop_tot-(pop_hit-list_hit)] ])
    _ , p_value = fisher_exact(data, alternative = 'two-sided')
    return p_value



def enrichment(request):
    genes = request.POST.get("analysisInput")
    genetype =  'genesymbol'
    genes = genes.split()
    genes = [x.strip() for x in genes]

    total_genes = len(genes)

    enrich = Enrich.objects.all().values('pmid','enrichment','count_total')

    if genetype == 'genesymbol':
        gene = Remembprot.objects.filter(geneSymbol__in = genes).values('geneSymbol','pmid')
        genetype = 'geneSymbol'
    else:
        gene = Remembprot.objects.filter(geneID__in = genes).values('geneID','pmid')
        genetype = 'geneID'

    main_df = pd.DataFrame(list(gene))
    enrich_df = pd.DataFrame(list(enrich))

    df = pd.merge(main_df,enrich_df, on = 'pmid')

    df = df[['enrichment',genetype,'count_total']]

    df = df.groupby('enrichment').agg({genetype:lambda x:list(set(x))})

    df['count'] = df[genetype].apply(lambda x: len(x))

    df.reset_index(inplace = True)

    df = df.merge(enrich_df[['enrichment','count_total']] , on ='enrichment')
    df['percentage'] = df['count'].apply(lambda x: (x/total_genes)*100)
    df['p_value'] = df.apply(lambda x: pvalue_calc(x['count'], x['count_total'],total_genes), axis=1)
    df['log10pval'] = abs(np.log10(df['p_value']))
    df.to_csv('check.csv')
    df['percentage'] = df['percentage'].apply(lambda x: "{:.2f}%".format(x))
    results = df[['enrichment','percentage','count','p_value']]

    results.sort_values('count', ascending = False , inplace = True)

    barplot = getbarplot(results[['enrichment','count','percentage']])

    enrichment_result = list()
    for index, row in results.iterrows():
        enrichment_result.append(row.to_dict())

    context = { 'enrichment_result':enrichment_result, 'barplot':barplot}
    return render(request,'rememb_prot/enrich_result.html', context)



def dose_ontology(request):

    if request.method == 'POST':
        genes = request.POST.get("doseInput")
        genes = genes.split()
        genes = [x.strip() for x in genes]
        genes = list(set(genes))
        dose = Dose.objects.filter(gene_symbol__in = genes ).values()
        df = pd.DataFrame(list(dose))
       
        df = df[['gene_symbol','description']]
        df['value'] = 1
        df = df.pivot(index = 'gene_symbol', columns='description')
        df.columns = df.columns.droplevel(0)
        df.fillna(0 , inplace = True)
        header_list = list(df.columns)
        # header_list.pop(0)
        df.reset_index(inplace = True)
        genes = df["gene_symbol"].tolist()
        # print(genes)
        df = df.set_index('gene_symbol')
        trans_df = df.transpose()
        
        nump = trans_df.to_numpy()
        dfg = pd.DataFrame(columns = genes)
        dfg.loc[0] = genes
        dfnew  = pd.concat([dfg,trans_df], axis=0)
        dfnew.reset_index(inplace=True)
        final_np = dfnew.to_numpy()
        final_np = np.delete(final_np, 0, 1)
        # print(final_np)
        final_np = final_np.transpose()
        
       
        return render(request, 'rememb_prot/dose_result.html',{'n':header_list,'genes':genes,'nump':nump, 'final_np':final_np})
        

def transmembrane(request):
    genes = request.POST.get("genefortrans")
    genes = genes.split()
    genes = [x.strip() for x in genes]
    transmemb = Remembprot.objects.filter(geneID__in = genes)
    context = {'transmemb':transmemb}
    return render(request,'rememb_prot/transmemb_done.html', context)


def bqueryResult(request):
    genes = request.POST.get("bqueryInput")
    species = request.POST.get("species")
    genes = genes.split()
    genes = [x.strip() for x in genes]
    main = Remembprot.objects.filter(Q(geneSymbol__in = genes) & Q(organism = species) ).values()
    cmData = Cellmarker.objects.filter(Q(geneSymbol__in = genes) & Q(species = species) ).values()
    main = pd.DataFrame(list(main))
    cmData = pd.DataFrame(list(cmData))
    if species in ['Homo sapiens', 'Mus musculus']:

        if len(main) == 0 or len(cmData) == 0:
            messages.error(request, 'Gene not found!') 
            return redirect('rememb_prot:bquery')
        results = main.merge(cmData, on = 'geneSymbol', how = 'left')
        results.fillna('-', inplace=True)
        results =  results.T.to_dict().values()
    else:
        if len(main) == 0 or len(cmData) == 0:
            messages.error(request, 'Gene not found!') 
            return redirect('rememb_prot:bquery')
        results = main
        results.fillna('-', inplace=True)
        results =  results.T.to_dict().values()
    
    
    context = {'results':results,'species':species}
    return render(request,'rememb_prot/bquery_result.html', context)


def selectedSpecies(request):
    if request.method == 'POST':
        species = request.POST.get("selectedSpecies")

        results = Remembprot.objects.filter(organism = species).values("protienExtractMethod").distinct()
        methods = pd.DataFrame(list(results))
        methods = methods['protienExtractMethod'].tolist()
        methods = [x.strip() for x in methods]
        data = dict()
        data['methods'] = methods
        return JsonResponse(data)



def selectedMethod(request):
    if request.method == 'POST':

        species = request.POST.get("selectedSpecies")

        method_selected = request.POST.get("methodSelect")
        results = Remembprot.objects.filter( Q(organism = species) & Q(protienExtractMethod = method_selected)).values("CellOrtissue").distinct()
        # print(results)
        cells = list()
        
        for item in results:
            cells.append(item['CellOrtissue'])
        
        data = dict()
 
        data['cells'] = cells
        return JsonResponse(data)


