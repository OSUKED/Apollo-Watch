call cd ..
call conda env create -f environment.yml
call conda activate Apollo
call ipython kernel install --user --name=Apollo
pause