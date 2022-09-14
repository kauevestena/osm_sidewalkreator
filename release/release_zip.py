import os, shutil
# from zipfile import ZipFile 
# thx: https://thispointer.com/python-how-to-create-a-zip-archive-from-multiple-files-or-directory/ 

from pathlib import Path

"""

    RELEASE SYSTEM FOR THE PLUGIN

    you just need to include in the list "exclude_patternslist" the patterns that should not be included in the release 

    it will export the zip file to a folder named "sidewalkreator_release" to the homefolder

"""



exclude_patternslist = ['.git','.github','__pycache__','notes','i18n','release','*.pyc','temporary','plugin_upload.py','trash','paper_publication','extra_tests']


# print(filelist)

this_file_path = os.path.realpath(__file__)
plugin_path = os.path.dirname(os.path.dirname(this_file_path))



destfolderpath = str(Path.home()/'sidewalkreator_release'/'osm_sidewalkreator'/'osm_sidewalkreator')

release_folderpath = str(Path(destfolderpath).parent)

outpath = os.path.join(os.path.expanduser("~"),'sidewalkreator_release','osm_sidewalkreator.zip')





if os.path.exists(release_folderpath):
    shutil.rmtree(release_folderpath)

#thx: https://stackoverflow.com/a/42488524/4436950
shutil.copytree(plugin_path,destfolderpath,ignore=shutil.ignore_patterns(*exclude_patternslist))

if os.path.exists(outpath):
    os.remove(outpath)



shutil.make_archive(outpath.replace('.zip',''),'zip',release_folderpath)

print(outpath)
print(release_folderpath)
print(destfolderpath)


