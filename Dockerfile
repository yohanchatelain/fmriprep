# Use Ubuntu 16.04 LTS
FROM ubuntu:xenial-20161213

# Installing ubuntu packages (FSL, AFNI, git)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl bzip2 ca-certificates && \
    curl -sSL http://neuro.debian.net/lists/xenial.us-ca.full >> /etc/apt/sources.list.d/neurodebian.sources.list && \
    apt-key adv --recv-keys --keyserver hkp://pgp.mit.edu:80 0xA5D32F012649A5A9 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
                    fsl-core=5.0.9-1~nd+1+nd16.04+1 \
                    git=1:2.7.4-0ubuntu1 \
                    afni=16.2.07~dfsg.1-2~nd16.04+1 \
                    graphviz=2.38.0-12ubuntu2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV FSLDIR=/usr/share/fsl/5.0
ENV FSLOUTPUTTYPE=NIFTI_GZ
ENV PATH=/usr/lib/fsl/5.0:$PATH
ENV FSLMULTIFILEQUIT=TRUE
ENV POSSUMDIR=/usr/share/fsl/5.0
ENV LD_LIBRARY_PATH=/usr/lib/fsl/5.0:$LD_LIBRARY_PATH
ENV FSLTCLSH=/usr/bin/tclsh
ENV FSLWISH=/usr/bin/wish
ENV FSLOUTPUTTYPE=NIFTI_GZ

# Installing and setting up ANTs
RUN mkdir -p /opt/ants && \
    curl -sSL "https://github.com/stnava/ANTs/releases/download/v2.1.0/Linux_Ubuntu14.04.tar.bz2" \
    | tar -xjC /opt/ants --strip-components 1

ENV ANTSPATH /opt/ants
ENV PATH $ANTSPATH:$PATH

# Installing and setting up c3d
RUN mkdir -p /opt/c3d && \
    curl -sSL "http://downloads.sourceforge.net/project/c3d/c3d/1.0.0/c3d-1.0.0-Linux-x86_64.tar.gz" \
    | tar -xzC /opt/c3d --strip-components 1

ENV C3DPATH /opt/c3d/
ENV PATH $C3DPATH/bin:$PATH

# Installing and setting up miniconda
RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-4.2.12-Linux-x86_64.sh && \
    bash Miniconda3-4.2.12-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-4.2.12-Linux-x86_64.sh

ENV PATH=/usr/local/miniconda/bin:$PATH \
	LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Installing precomputed python packages
RUN conda config --add channels intel
ENV ACCEPT_INTEL_PYTHON_EULA=yes
RUN umask 000
RUN conda install -y mkl=2017.0.1 \
                     numpy=1.11.2 \
                     scipy=0.18.1 \
                     scikit-learn=0.17.1 \
                     matplotlib=1.5.3 \
                     pandas=0.19.0 \
                     libxml2=2.9.4 \
                     libxslt=1.1.29 \
                     traits=4.6.0 && \
    conda clean --all -y

# Precaching fonts
RUN python -c "from matplotlib import font_manager"

# Unless otherwise specified each process should only use one thread - nipype
# will handle parallelization
ENV MKL_NUM_THREADS=1
ENV OMP_NUM_THREADS=1

# Installing dev requirements (packages that are not in pypi)
ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt && \
    rm -rf ~/.cache/pip

# Precaching atlases
RUN mkdir /niworkflows_data
ENV CRN_SHARED_DATA /niworkflows_data
RUN python -c 'from niworkflows.data.getters import get_mni_template_ras; get_mni_template_ras()' && \
    python -c 'from niworkflows.data.getters import get_mni_icbm152_nlin_asym_09c; get_mni_icbm152_nlin_asym_09c()' && \
    python -c 'from niworkflows.data.getters import get_ants_oasis_template_ras; get_ants_oasis_template_ras()'

# Installing FMRIPREP
COPY . /root/src/fmriprep
RUN cd /root/src/fmriprep && \
    pip install -e .[all] && \
    rm -rf ~/.cache/pip

# Precompiling (creating.pyc files)
RUN python -m compileall /root/src/fmriprep
RUN python -m compileall

WORKDIR /root/src/fmriprep

ENTRYPOINT ["/usr/local/miniconda/bin/fmriprep"]

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="FMRIPREP" \
      org.label-schema.description="FMRIPREP - robust fMRI preprocessing tool" \
      org.label-schema.url="http:/fmriprep.readthedocs.io" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.vcs-url="https://github.com/poldracklab/fmriprep" \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0"