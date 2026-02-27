:: git init

:: git remote add origin https://github.com/ougwon/test.git

:: git add --all

:: git commit -m "before reupload"

:: git pull --rebase origin main

:: git push --set-upstream origin main

:loop

	cd D:\My Java\algorithm

	git add --all

	git commit -m "auto commit"

	git pull

	git push
	
	TIMEOUT 300

goto loop