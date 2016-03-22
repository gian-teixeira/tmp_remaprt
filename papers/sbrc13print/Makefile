LATEX=latex
BIBTEX=bibtex
DVIPDFM=dvipdfm
DVIPS=dvips

EXTRAFILES=$(wildcard *.tex)

BASENAME=paper
BIBNAME=references.bib

all:
	latex $(BASENAME)
	bibtex $(BASENAME)
	latex $(BASENAME)
	latex $(BASENAME)
	dvipdf $(BASENAME).dvi
	cp $(BASENAME).pdf ~/windows/Desktop

open:
	gv main.ps &

clean:
	\rm -rf $(BASENAME).aux $(BASENAME).dvi $(BASENAME).log $(BASENAME).bbl $(BASENAME).out $(BASENAME).blg $(BASENAME).ps $(BASENAME).pdf *~


#	bibtex $(BASENAME)
