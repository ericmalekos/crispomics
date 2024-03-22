#!/usr/bin/env python3

import argparse
import pandas as pd

'''
../scripts/gtf_from_ribotish.py -r GSE208041_merged_AllORFs.tsv -i gencode.v41.annotation.gtf \
    -o output.gtf --max_frameqvalue 0.05 --min_inframecount 20 --min_aalen 50 \
    --select_based_on AALen --genetype protein_coding  --tistype "5'UTR"

'''

def parse_arguments():
    parser = argparse.ArgumentParser(description="Convert Ribotish TSV to GTF, with filtering and selection options.")
    parser.add_argument("-r", "--ribotish", required=True, help="Path to the Ribotish predict TSV file")
    parser.add_argument("-i", "--input_gtf", required=True, help="Path to the corresponding GTF file")  # Fixed
    parser.add_argument("-o", "--output_gtf", required=True, help="Path to output the new GTF file")  # Fixed
    parser.add_argument("--min_aalen", type=int, default=1, help="Minimum amino acid length")
    parser.add_argument("--min_inframecount", type=int, default=1, help="Minimum in-frame count")
    parser.add_argument("--max_tisqvalue", type=float, default=1.0, help="Maximum TIS Q-value")
    parser.add_argument("--max_frameqvalue", type=float, default=1.0, help="Maximum Frame Q-value")
    parser.add_argument("--max_fisherqvalue", type=float, default=1.0, help="Maximum Fisher Q-value")
    parser.add_argument("--select_based_on", required=True, choices=['AALen', 'InFrameCount', 'TISQvalue', 'FrameQvalue', 'FisherQvalue'], help="Column to select the best row for each Tid, TisType pair")
    parser.add_argument("--genetype", help="GeneType to filter, must match a column entry")
    parser.add_argument("--tistype", required=True, help="TisType to filter, must match a column entry")

    return parser.parse_args()

def load_ribotish_data(ribotish_file):
    return pd.read_csv(ribotish_file, sep='\t')

def filter_and_select_data(df, args):
    # Convert "None" strings to actual None (NaN) for relevant columns
    for col in ['TISQvalue', 'FrameQvalue', 'FisherQvalue']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    filtered_df = df[(df['AALen'] >= args.min_aalen) &
                     (df['InFrameCount'] >= args.min_inframecount) &
                     ((df['TISQvalue'] <= args.max_tisqvalue) if df['TISQvalue'].notna().any() else True) &
                     ((df['FrameQvalue'] <= args.max_frameqvalue) if df['FrameQvalue'].notna().any() else True) &
                     ((df['FisherQvalue'] <= args.max_fisherqvalue) if df['FisherQvalue'].notna().any() else True)]

    if args.genetype:
        filtered_df = filtered_df[filtered_df['GeneType'] == args.genetype]
    if args.tistype:
        filtered_df = filtered_df[filtered_df['TisType'] == args.tistype]
    
    # Select the best row for each Tid, TisType pair based on user-defined criteria
    best_rows = filtered_df.sort_values(by=args.select_based_on, ascending=False).drop_duplicates(subset=['Tid', 'TisType'])
    
    return best_rows

def convert_to_gtf(df, input_gtf_path, output_gtf_path):
    gtf_columns = ['seqname', 'source', 'feature', 'start', 'end', 'score', 'strand', 'frame', 'attribute']
    # Read the GTF with QUOTE_NONE to handle quotes in attributes correctly
    gtf_df = pd.read_csv(input_gtf_path, sep='\t', comment='#', header=None, names=gtf_columns, quoting=3, dtype={'start': int, 'end': int})
    
    # Extract transcript_id for filtering
    gtf_df['transcript_id'] = gtf_df['attribute'].str.extract('transcript_id "([^"]+)"')
    
    # Keep only relevant transcript and exon entries
    relevant_gtf_df = gtf_df[gtf_df['transcript_id'].isin(df['Tid']) & gtf_df['feature'].isin(['transcript', 'exon'])]

    with open(output_gtf_path, 'w') as out_file:
        # Write filtered transcript and exon entries to the output GTF
        for _, row in relevant_gtf_df.iterrows():
            out_file.write('\t'.join(map(str, row[:9])) + '\n')  # Ensure all columns up to 'attribute' are written
        
        # Append new CDS entries for each relevant transcript based on the Blocks column from the Ribotish TSV
        for _, ribo_row in df.iterrows():
                    for block in ribo_row['Blocks'].split(','):
                        start, end = block.split('-')
                        start = str(int(start) + 1)
                        attributes = f'gene_id "{ribo_row["Gid"]}"; transcript_id "{ribo_row["Tid"]}"; gene_name "{ribo_row["Symbol"]}";'
                        if 'GeneType' in df.columns:  # Check if GeneType column exists
                            attributes += f' gene_type "{ribo_row["GeneType"]}";'
                        else:
                            attributes += ' gene_type "unknown";'  # Fallback if GeneType not in Ribotish data
                        # Construct and write the GTF line for CDS
                        gtf_line = f'{ribo_row["GenomePos"].split(":")[0]}\tribotish\tCDS\t{start}\t{end}\t.\t{ribo_row["GenomePos"].split(":")[2]}\t0\t{attributes}\n'
                        out_file.write(gtf_line)
def main():
    args = parse_arguments()
    ribotish_df = load_ribotish_data(args.ribotish)
    filtered_selected_df = filter_and_select_data(ribotish_df, args)
    filtered_selected_df.to_csv('filtered_' + args.ribotish, sep = '\t', )
    convert_to_gtf(filtered_selected_df, args.input_gtf, args.output_gtf)

if __name__ == "__main__":
    main()