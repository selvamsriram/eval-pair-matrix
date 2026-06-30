SRC = eval_pair_matrix_acl_final_revision.tex

all: preprint review

# arXiv / camera-ready: named authors, no line numbers (default mode)
preprint:
	latexmk -pdf -jobname=eval_pair_matrix_acl_final_revision_preprint $(SRC)

# ACL submission: anonymous, line numbers (sets \submissionmode)
review:
	latexmk -pdf -usepretex='\def\submissionmode{}' \
		-jobname=eval_pair_matrix_acl_final_revision_review $(SRC)

clean:
	latexmk -C -jobname=eval_pair_matrix_acl_final_revision_preprint $(SRC)
	latexmk -C -jobname=eval_pair_matrix_acl_final_revision_review $(SRC)

.PHONY: all preprint review clean
