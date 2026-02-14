from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, Field

from workflow import run_workflow


app = FastAPI(title="XHS Remix Workflow", version="1.0.0")


class RemixRequest(BaseModel):
    note_url: HttpUrl
    theme: str = Field(min_length=2, max_length=30)
    extra_edit_prompt: str | None = Field(default=None, max_length=200)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/remix")
def remix(request: RemixRequest) -> dict:
    try:
        result = run_workflow(
            note_url=str(request.note_url),
            theme=request.theme,
            extra_edit_prompt=request.extra_edit_prompt,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"workflow failed: {exc}") from exc

    return {
        "job_id": result.job_id,
        "output_link": str(result.output_dir),
        "zip_link": str(result.zip_file),
        "note_file": str(result.note_file),
        "images": [str(i) for i in result.images],
    }
