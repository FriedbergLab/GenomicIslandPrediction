import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="treasureisland",                     # This is the name of the package
    version="1.1.5",                        # The initial release version
    author="Priyanka Banerjee",
    author_email="banerjee.p1104@gmail.com",                     # Full name of the author
    description="Prediction of Genomic Islands",
    url = 'https://github.com/priyamayur/GenomicIslandPrediction',
    long_description=long_description,      # Long description read from the the readme file
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),    # List of all python modules to be installed
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],                                      # Information to filter the project on PyPi website
    python_requires='>=3.7',                # Minimum version requirement of the package
    py_modules=["treasureisland"],
    entry_points = {
        'console_scripts': ['treasureisland=treasureisland.treasureisland:main'],
    },
    include_package_data=True,
    install_requires=[
        'gensim>=4.3.2',
        'biopython>=1.79',
        'scikit-learn>=1.4.0',
        'pandas',
        'openpyxl',
        'importlib-resources',
        'numpy>=1.26.3',
        'tqdm'
   ]
)
