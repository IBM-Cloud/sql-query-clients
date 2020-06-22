# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
#SPHINXBUILD   = sphinx-build
SPHINXBUILD   = python3 -msphinx
SPHINXPROJ    = SQLClient
SOURCEDIR     = source
#BUILDDIR      = build
BUILDDIR      = /tmp/sql-query-clients-docs
PDFBUILDDIR  = /tmp
PDF          = ../manual.pdf

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

$(BUILDDIR)/html:
	mkdir $(BUILDDIR)
	cd $(BUILDDIR); git clone git@github.com:IBM-Cloud/sql-query-clients.git html; cd html; git checkout -b gh-pages remotes/origin/gh-pages

html: | $(BUILDDIR)/html
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Internal variables.
PAPEROPT_a4     = -D latex_paper_size=a4
PAPEROPT_letter = -D latex_paper_size=letter
ALLSPHINXOPTS   = -d $(BUILDDIR)/doctrees $(PAPEROPT_$(PAPER)) $(SPHINXOPTS) source

setup:
	conda create -n sphinx python=3.6 
	conda activate sphinx
	pip install m2r recommonmark sphinx==2.4.4 --force-reinstall
	echo Make sure you're in 'sphinx' virtual environment each time you build the docs

latexpdf:
	$(SPHINXBUILD) -b latex $(ALLSPHINXOPTS) $(PDFBUILDDIR)/latex
	@echo "Running LaTeX files through pdflatex..."
	make -C $(PDFBUILDDIR)/latex all-pdf
	cp $(PDFBUILDDIR)/latex/*.pdf $(PDF)
	@echo "pdflatex finished; see PDF files in $(PDF)"
python:
	rm source/ibmcloudsql.rst
	sphinx-apidoc -f -o source ../Python/ibmcloudsql ... ../Python/ibmcloudsql/test*

buildandcommithtml: html 
	cd $(BUILDDIR)/html; git add . ; git commit -m "rebuilt docs"; git push origin gh-pages
	echo Goto https://pages.github.ibm.com/IoT-Edge/edgeai-core/ to see the new docs.
		 echo Goto https://ibm-cloud.github.io/sql-query-clients/ to see the new docs.
