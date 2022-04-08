'''
    script only intended to generate a filetree to decide which file should go to the zip package to update package in the qgis plugins
'''

import os

this_file_path = os.path.realpath(__file__)
# thx: https://stackoverflow.com/a/595332/4436950

rootpath = os.path.dirname(os.path.dirname(this_file_path))
# thx: https://stackoverflow.com/a/10149358/4436950

filelist = []

excludedirlist = ['.git','__pycache__','notes','i18n','release','temporary','*.pyc']

for dirpath,subdirnames,files in os.walk(rootpath,):
    # thx: thispointer.com

    filelist += [os.path.join(dirpath,file) for file in files if not any(excluder in dirpath for excluder in excludedirlist)]


outpath = os.path.join(rootpath,'release/filelist.py')

with open(outpath,'w+') as pathwriter:
    pathwriter.write('"""\nyou just need to comment the lines with files you wanna exclude from release\n"""\n\nfilelist = [\n')

    for item in filelist:
        pathwriter.write(f'"{item}",\n')

    pathwriter.write(']')
    

