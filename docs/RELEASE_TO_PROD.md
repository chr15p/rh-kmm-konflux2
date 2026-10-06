To release to production:

1) find the last relase to staging that was tested by QE 


2) determine the SNAPSHOT it released and the RELEASE (e.g r26)

2) run the release script:
```
scripts/release.py  --snapshot  $SNAPSHOT  --application kmm-2-5 --env prod  --token $(konflux whoami -t ) --release 26  --commit 63b16d73364a52b60c3fab420f13079dc76ef81c
```
--release is just an identifier to ensure names are unique but its nice to keep it in sync with the staging release

--commit is the commit that is HEAD of the repo (its really only used for labelling the release object so you can get it wrong, it will just be confusing)

3) wait for the release to succeed

4) update config/pullspecs.json to move the x.y.z number out of "stage:[]" into "prod:[]"  (this ensures it gets named registry.redhat.io... in the FBC rather thatn registry.stage.redhat.io)

4) trigger the FBCs to rebuild

5) wait for the FBCs to finish building

6) release the FBCs to prod
```
scripts/release_fbc.py --token $(konflux whoami -t) --env prod
```
