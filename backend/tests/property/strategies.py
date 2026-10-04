"""Shared Hypothesis strategies for the property tests (design.md §17, NFR3).

Inputs mix realistic data (catalog skills, aliases, common roles and cities) with arbitrary
Unicode so the engine is exercised on both. Collision cases are built in on purpose: project
names and target roles that are equal after casefold but differ in original text, and roles
made only of stop tokens.
"""

from hypothesis import strategies as st

from app.services.matching import normalize_skill
from app.services.matching.skill_catalog import ALIASES, CATALOG
from app.services.matching.types import (
    EducationLevel,
    ExperienceLevel,
    MatchJob,
    MatchProfile,
    ProjectInput,
    WorkMode,
)

CATALOG_NAMES: tuple[str, ...] = tuple(sorted(CATALOG))
ALIAS_NAMES: tuple[str, ...] = tuple(sorted(ALIASES))
# Wrappers from design.md §17 P3: `" React ,"`, `"(React)"`, `"React."` and friends.
EDGE_WRAPPERS: tuple[tuple[str, str], ...] = (
    (" ", " ,"),
    ("(", ")"),
    ("", "."),
    ("[", "];"),
    ('"', '"'),
    ("  ", "  |"),
    ("{", "}."),
)
ROLE_SAMPLES: tuple[str, ...] = (
    "Backend Engineer",
    "backend engineer",
    "BACKEND ENGINEER",
    "Frontend Developer",
    "front-end developer",
    "Full Stack Engineer",
    "Data Analyst",
    "Machine Learning Engineer",
    "Software Engineer Intern",
    "SWE",
)
STOP_TOKEN_ROLES: tuple[str, ...] = ("Intern", "Senior Junior", "Lead", "Graduate Trainee II")
PROJECT_NAME_SAMPLES: tuple[str, ...] = (
    "Chat App",
    "chat app",
    " CHAT APP ",
    "Portfolio",
    "portfolio",
    "Data Pipeline",
)
LOCATION_SAMPLES: tuple[str, ...] = (
    "Berlin, Germany",
    "berlin, germany",
    "Munich, Germany",
    "London, UK",
    "Remote",
    "Bengaluru, India",
    "",
)

_ascii_word = st.from_regex(r"[a-z][a-z0-9+#]{0,14}", fullmatch=True)

# Skills that behave like real input: catalog names, aliases and plain ASCII words.
realistic_skills = st.one_of(
    st.sampled_from(CATALOG_NAMES), st.sampled_from(ALIAS_NAMES), _ascii_word
)
# Any skill string, including arbitrary Unicode and over-long text.
skill_texts = st.one_of(realistic_skills, st.text(max_size=60))
skill_tuples = st.lists(skill_texts, max_size=8).map(tuple)

roles = st.one_of(
    st.sampled_from(ROLE_SAMPLES), st.sampled_from(STOP_TOKEN_ROLES), st.text(max_size=40)
)
locations = st.one_of(st.sampled_from(LOCATION_SAMPLES), st.text(max_size=30))
work_modes = st.sampled_from(WorkMode)
experience_levels = st.none() | st.sampled_from(ExperienceLevel)
education_levels = st.none() | st.sampled_from(EducationLevel)

projects = st.builds(
    ProjectInput,
    name=st.one_of(st.sampled_from(PROJECT_NAME_SAMPLES), st.text(max_size=20)),
    technologies=st.lists(skill_texts, max_size=3).map(tuple),
)

profiles = st.builds(
    MatchProfile,
    technical_skills=skill_tuples,
    target_roles=st.lists(roles, max_size=4).map(tuple),
    location=st.none() | locations,
    preferred_locations=st.lists(locations, max_size=3).map(tuple),
    preferred_work_modes=st.lists(work_modes, max_size=3).map(tuple),
    experience_level=experience_levels,
    education_level=education_levels,
    projects=st.lists(projects, max_size=20).map(tuple),
)

jobs = st.builds(
    MatchJob,
    id=st.integers(min_value=1, max_value=10_000),
    title=roles,
    location=locations,
    work_mode=work_modes,
    experience_level=experience_levels,
    min_education_level=education_levels,
    required_skills=skill_tuples,
    preferred_skills=skill_tuples,
)


def _aliases_of(canonical: str) -> tuple[str, ...]:
    return tuple(alias for alias in ALIAS_NAMES if ALIASES[alias] == canonical)


@st.composite
def skill_variant(draw: st.DrawFn, skill: str) -> str:
    """A spelling of `skill` that normalizes to the same canonical name."""
    canonical = normalize_skill(skill)
    options = [skill, skill.upper(), f"  {skill}\t"]
    options += [prefix + skill + suffix for prefix, suffix in EDGE_WRAPPERS]
    if canonical is not None:
        options += list(_aliases_of(canonical))
    return draw(st.sampled_from(options))


@st.composite
def skill_variants(draw: st.DrawFn, skills: tuple[str, ...]) -> tuple[str, ...]:
    """`skills` plus duplicates and variants, shuffled; same set of normalized names."""
    expanded = list(skills)
    for skill in skills:
        expanded += draw(st.lists(skill_variant(skill), max_size=3))
    return tuple(draw(st.permutations(expanded)))


@st.composite
def permuted_profile(draw: st.DrawFn, profile: MatchProfile) -> MatchProfile:
    """`profile` with every tuple (including project technologies) reordered."""
    shuffled_projects = tuple(
        ProjectInput(p.name, tuple(draw(st.permutations(p.technologies))))
        for p in draw(st.permutations(profile.projects))
    )
    return MatchProfile(
        technical_skills=tuple(draw(st.permutations(profile.technical_skills))),
        target_roles=tuple(draw(st.permutations(profile.target_roles))),
        location=profile.location,
        preferred_locations=tuple(draw(st.permutations(profile.preferred_locations))),
        preferred_work_modes=tuple(draw(st.permutations(profile.preferred_work_modes))),
        experience_level=profile.experience_level,
        education_level=profile.education_level,
        projects=shuffled_projects,
    )


@st.composite
def permuted_job(draw: st.DrawFn, job: MatchJob) -> MatchJob:
    """`job` with its skill tuples reordered."""
    return MatchJob(
        id=job.id,
        title=job.title,
        location=job.location,
        work_mode=job.work_mode,
        experience_level=job.experience_level,
        min_education_level=job.min_education_level,
        required_skills=tuple(draw(st.permutations(job.required_skills))),
        preferred_skills=tuple(draw(st.permutations(job.preferred_skills))),
    )
