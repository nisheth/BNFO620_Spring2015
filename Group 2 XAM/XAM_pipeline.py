#!/usr/bin/env python
# Written by: Shaun Norris
# VCU BNFO 620 - Bioinformatics practicum
# Group 2 - XAM Pipeline

### Imports ###
import subprocess,sys,re
### Global Variables/Constants ###
try:
	F1 = sys.argv[1]
	F2 = sys.argv[2]
	REF = sys.argv[3]
	SB = sys.argv[4]
	SNAME = sys.argv[5]
except:
	print "Not enough arguments provided... Usage: XAM_pipeline.py file1.fastq file2.fastq reference.fa outfilename samplename"
	sys.exit(1)
bwapath="/usr/global/blp/bin/bwa"
sampath="/usr/global/blp/bin/samtools"
java="java"
picardpath="/usr/global/blp/picard-tools-1.95/"
GATK="/usr/global/blp/GenomeAnalysisTK-3.1.1/GenomeAnalysisTK.jar"
### Functions ###
def QC():
	try:
		print "Running FastQC..."
		subprocess.Popen(['fastqc',F1,F2]).wait()
	except:
		print "FastQC Failed..."
	#pass
def align():
	RG = '@RG\\tID:%s_%s_%s\\tLB:%s\\tSM:%s\\tPL:ILLUMINA' % (SNAME,SNAME,SNAME,SNAME,SNAME)
	merged = SNAME + '_aligned.sam'
	mergedfile = open(merged,'w')
	print "Running bwa alignment..."
	#print bwapath,'mem','-t','10',REF,'-R',RG,F1,F2,'>',merged
	memalign = subprocess.Popen(['bwa','mem','-t','20','-M',REF,'-R',RG,F1,F2], stdout=subprocess.PIPE)#,stdin=subprocess.PIPE,stderr=subprocess.PIPE).wait() #maybe use .call?
	memout = memalign.communicate()[0]
	mergedfile.write(memout)
	return merged
#	except:
#		print "Alignment Failed..."
#		sys.exit()
def sam2bam(merged):
	print "Converting SAM to BAM..."
	BAM = merged.strip('.sam') + '.bam'
	subprocess.Popen([sampath,'view','-bS',merged,'-o',BAM]).wait()
	return BAM
def sort(BAM):
	print "Sorting BAM File..."
	SORTED = BAM.strip('.bam') + '_sorted'
	subprocess.Popen([sampath,'sort',BAM,SORTED]).wait()
	return SORTED
def readgroups(SORTED):
	# Not used anymore #
	print "Changing Read Groups..."
	picardjar = picardpath + "AddOrReplaceReadGroups.jar"
	subprocess.Popen([java,picardjar,'INPUT=%s_sorted.bam','OUTPUT=%s_sorted_grouped.bam','SORT_ORDER=coordinate','RGLB=8','RGPL=Illumina','RGPU=1','RGSM=%s' % (SNAME,SNAME)]).wait()
def rmv_dups(SORTED):
	picardjar = picardpath + "MarkDuplicates.jar"
	print "Removing Duplicate Reads..."
	MOUT = 'M=' + SNAME + '_dup_mets.out'
	IN = 'I=' + SORTED + '.bam'
	OUT = 'O=' + SNAME +'.nodup.bam'
	subprocess.Popen([java,'-Xmx6g','-jar',picardjar,'REMOVE_DUPLICATES=true',MOUT,IN,OUT]).wait()
	return (SNAME + '.nodup.bam')
def index(NODUPS):
	print NODUPS
	INPUT = 'I=' + NODUPS 
	print "Creating Index..."
	picardjar = picardpath + "BuildBamIndex.jar"
	subprocess.Popen([java,'-Xmx6g','-jar',picardjar,INPUT]).wait()
def index_stats(IDX):
	print "Running Index stats..."
	picardjar = picardpath + "BamIndexStats.jar"
	INPUT = 'INPUT=' + IDX
	OUTPUT = SNAME + '.bam_IDXstats.txt'
	outfile = open(OUTPUT,'w')
	idx_p = subprocess.Popen([java,'-Xmx6g','-jar',picardjar,INPUT], stdout=subprocess.PIPE)
	idxout = idx_p.communicate()[0]
	outfile.write(idxout)
def validate(NODUPS):
	print "Validating BAM File..."
	picardjar = picardpath + "ValidateSamFile.jar"
	INPUT = 'INPUT=' + NODUPS
	subprocess.Popen([java,'-Xmx6g','-jar',picardjar,INPUT]).wait()
def seq_dict():
	print "Generating the Sequence Dictionary..."
	picardjar = picardpath + "CreateSequenceDictionary.jar"
	REFERENCE = 'REFERENCE=%s' % REF
	OUTPUT = 'OUTPUT=%s.dict' % REF
	subprocess.Popen([java,'-Xmx6g','-jar',picardjar,REFERENCE,OUTPUT]).wait()
def fasta_idx():
	print "Creating index..."
	subprocess.Popen([sampath,'faidx',REF]).wait()
def reorder(NODUPS):
	print "Reordering BAM file..."
	picardjar = picardpath + "ReorderSam.jar"
	INPUT = 'I=' + NODUPS
	OUTPUT = 'O=%s.nodup_reorder.bam' % SNAME
	REFERENCE = 'R=' + REF
	subprocess.Popen([java,'-Xmx6g','-jar',picardjar,INPUT,OUTPUT,REFERENCE]).wait()
	return ('%s.nodup_reorder.bam' % SNAME)
def realign(REORDER):
	print "Running Realignment..."
	print REORDER
	picardjar = picardpath + "FixMateInformation.jar"
	OUTLIST = '%s.bam.list' % SNAME
	REALIGNED = '%s.realigned.bam' % SNAME
	print java,'-Xmx6g','-jar',GATK,'-T','RealignerTargetCreator','-R',REF,'-o',OUTLIST,'-I',REORDER
	#subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','RealignerTargetCreator','-R',REF,'-o',OUTLIST,'-I',REORDER]).wait()
	#subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','IndelRealigner','-targetIntervals',OUTLIST,'-I',REORDER,'-R',REF,'-o',REALIGNED]).wait()
	INPUT = "INPUT=%s" % REALIGNED
	OUTPUT = "OUTPUT=%s.realigned_fixmate.bam" % SNAME
	print java,picardjar,INPUT,OUTPUT,'SO=coordinate','VALIDATION_STRINGENCY=LENIENT','CREATE_INDEX=true'
	subprocess.Popen([java,'-Xmx6g','-jar',picardjar,INPUT,OUTPUT,'SO=coordinate','VALIDATION_STRINGENCY=LENIENT','CREATE_INDEX=true']).wait()
	return "%s.realigned_fixmate.bam" % SNAME
def recalibrate(REALIGNED):
	print "Running base recalibration..."
	RECALOUT = "%s.recal.table" % SNAME
	KNOWNSITES = "/gpfs_fs/bnfo620/exome_data/Mills_and_1000G_gold_standard.indels.hg19.sites.vcf"
	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','BaseRecalibrator','-I',REALIGNED,'-R',REF,'-o',RECALOUT,'-knownSites',KNOWNSITES]).wait()
def rescore(REALIGNED):
	print "Running base quality score recalibration..."
	RESCORE = "%s_rescored.bam" % SNAME
	REPORT = "%s_recal_report.txt" % SNAME
	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','PrintReads','-R',REF,'-I',REALIGNED,'-BQSR',REPORT,'-o',RESCORE]).wait()
	return RESCORE
def snps_indels(RESCORE):
	print "Running SNP and InDels analysis"
	INDELS = "%s_indels.txt" % SNAME
	INDELSTATS = "%s_indels_stats.txt" % SNAME
	VARIANTS = "%s_variants.vcf" % SNAME
	CALLS = "%s.calls.geli" % SNAME
	KNOWNSITES = "/gpfs_fs/bnfo620/exome_data/Mills_and_1000G_gold_standard.indels.hg19.sites.vcf"
	VARIANTANNO = "%s_annotated.vcf" % SNAME
	RECALOUT_IND = "%s_INDEL.recal" % SNAME
	TRANCHESOUT_IND = "%s_INDEL.tranches" % SNAME
	RECALOUT_SNP = "%s_INDEL.recal" % SNAME
	TRANCHESOUT_SNP = "%s_INDEL.tranches" % SNAME
	OMNI = "/gpfs_fs/bnfo620/exome_data/Mills_and_1000G_gold_standard.indels.hg19.sites.vcf"
	HAPMAP = VARIANTANNO
	DBSNP = "dbsnp_138.hg19.vcf"
	RSCRIPT_IND = "%s_INDEL_plots.R" % SNAME
	RSCRIPT_SNP = "%s_SNP_plots.R" % SNAME
	INDVCF = "%s_indels.vcf" % SNAME
	SNPVCF = "%s_SNP.vcf" % SNAME
	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','HaplotypeCaller','-R',REF,'-I',RESCORE,'--genotyping_mode','DISCOVERY','-o',VARIANTS]).wait()	## FILTER THIS ?!?
	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','VariantRecalibrator','-R',REF,'-input',VARIANTS,'-recalFile',RECALOUT_IND,'-tranchesFile',TRANCHESOUT_IND,'--maxGaussians','4','-resource:hapmap,known=false,training=true,truth=true,prior=15.0',HAPMAP,'-resource:omni,known=false,training=true,truth=false,prior=12.0',OMNI,'-resource:dbsnp,known=true,training=false,truth=false,prior=2.0',DBSNP,'-an','MQ','-mode','INDEL','-an','QD','-an','DP','-an','FS','-an','SOR','-an','ReadPosRankSum','-an','MQRankSum','-an','InbreedingCoeff','-rscriptFile',RSCRIPT_IND]).wait() # INDELS
	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','ApplyRecalibration','-R',REF,'-input',VARIANTS,'-mode','INDEL','-recalFile',RECALOUT_IND,'-tranchesFile',TRANCHESOUT_IND,'-o',INDVCF,'-ts_filter_level','99.0']).wait() #APPLY RECAL FOR INDELS
	
	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','VariantRecalibrator','-R',REF,'-input',VARIANTS,'-recalFile',RECALOUT_SNP,'-tranchesFile',TRANCHESOUT_SNP,'--maxGaussians','4','-resource:hapmap,known=false,training=true,truth=true,prior=15.0',HAPMAP,'-resource:omni,known=false,training=true,truth=false,prior=12.0',OMNI,'-resource:dbsnp,known=true,training=false,truth=false,prior=6.0',DBSNP,'-mode','SNP','-an','QD','-an','MQ','-an','HaplotypeScore','-rscriptFile',RSCRIPT_SNP]).wait() #SNPS

	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','ApplyRecalibration','-R',REF,'-input',VARIANTS,'-mode','SNP','-recalFile',RECALOUT_SNP,'-tranchesFile',TRANCHESOUT_SNP,'-o',SNPVCF,'-ts_filter_level','99.0']).wait() # APPLY RECAL FOR SNPS
	#APPLY RECAL
	subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','VariantAnnotator','-R',REF,'-I',RESCORE,'--variant',KNOWNSITES,'-o',VARIANTANNO]).wait()
##NO LONGER USED##
	#subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','IndelGenotyperV2','-R',REF,'-I',RESCORE,'-O',INDELS,'--verbose','-o',INDELSTATS]).wait()
	#subprocess.Popen([java,'-Xmx6g','-jar',GATK,'-T','UnifiedGenotyper','-R',REF,'-I',RESCORE,'-varout',CALLS,'-vf','GELI','-stand_call_conf','30.0','-stand_emit_conf','10.0','-pl','SOLEXA']).wait()	
################
#### Call Functions ####
QC()
merged = align()
BAM = sam2bam(merged)
SORTED = sort(BAM)
#readgroups(SORTED) #SHOULD NO LONGER BE NECESSARY
NODUPS = rmv_dups(SORTED)
index(NODUPS)
index_stats(NODUPS)
#seq_dict() #Only needs to run once
#fasta_idx() #Only needs to run once
REORDER = reorder(NODUPS)
validate(NODUPS)
index(REORDER)
index_stats(REORDER)
REALIGNED = realign(REORDER)
recalibrate(REALIGNED)
RESCORE = rescore(REALIGNED)
snps_indels(RESCORE)
