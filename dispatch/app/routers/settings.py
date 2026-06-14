from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from ..scoring.engine import rescore_all
from ..integrations import eia, fmcsa
from ..ai import negotiate
from .. import models, config

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def settings_form(request: Request, db: Session = Depends(get_db)):
    s = db.get(models.Settings, 1)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "s": s,
            "diesel_cpg": eia.current_cpg(db),
            "eia_configured": bool(config.EIA_API_KEY),
            "fmcsa_configured": fmcsa.configured(),
            "ai_configured": negotiate.configured(),
            "routing": "ORS" if config.ORS_API_KEY else ("OSRM" if config.OSRM_URL else "great-circle fallback"),
        },
    )


@router.post("/")
def save_settings(
    mpg: float = Form(...),
    fixed_monthly: float = Form(...),
    avg_monthly_miles: int = Form(...),
    maint_cpm: int = Form(...),
    target_margin_pct: int = Form(...),
    factoring_pct: float = Form(3.0),
    avg_speed_mph: float = Form(50.0),
    detention_free_hours: float = Form(2.0),
    detention_rate: float = Form(75.0),
    db: Session = Depends(get_db),
):
    s = db.get(models.Settings, 1)
    s.mpg = mpg
    s.fixed_monthly_cents = int(round(fixed_monthly * 100))
    s.avg_monthly_miles = avg_monthly_miles
    s.maint_cpm_cents = maint_cpm
    s.target_margin_pct = target_margin_pct
    s.factoring_pct = factoring_pct
    s.avg_speed_mph = avg_speed_mph
    s.detention_free_hours = detention_free_hours
    s.detention_rate_cents = int(round(detention_rate * 100))
    db.commit()
    rescore_all(db)  # economics changed — refresh every load's numbers
    return RedirectResponse("/settings/", status_code=303)


@router.post("/refresh-fuel")
def refresh_fuel(db: Session = Depends(get_db)):
    eia.refresh(db)
    rescore_all(db)
    return RedirectResponse("/settings/", status_code=303)
