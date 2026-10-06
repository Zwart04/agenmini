package main

import (
	"9router/proxy/internal/app"
	"log"
)

func main() {
	p := app.DefaultCLIParams()
	p.RTK = false
	p.RTKSet = true
	p.Caveman = false
	p.CavemanSet = true
	p.Ponytail = false
	p.PonytailSet = true
	p.ADHD = false
	p.ADHDSet = true
	p.AutoUpdate = false
	if err := app.Run(app.NewApp(p)); err != nil {
		log.Fatal(err)
	}
}
