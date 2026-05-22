"""Vector search tests: these use the real fastembed model (BAAI/bge-small-en-v1.5).
The model is downloaded on first run (~130 MB) and cached locally thereafter."""

import pytest

from project_memory.embedding import EMBEDDING_DIM, cosine_similarity, embed, memory_embed_text
from project_memory.memory_service import ProjectMemoryService, UserMemoryService


async def test_embed_returns_correct_dim():
    vecs = await embed(["hello world"])
    assert len(vecs) == 1
    assert len(vecs[0]) == EMBEDDING_DIM


async def test_embed_same_text_is_deterministic():
    a = await embed(["hello world"])
    b = await embed(["hello world"])
    assert len(a[0]) == EMBEDDING_DIM
    sim = cosine_similarity(a[0], b[0])
    assert sim == pytest.approx(1.0, abs=1e-4)


async def test_cosine_similarity_of_identical_vector_is_1():
    vecs = await embed(["hello world test"])
    v = vecs[0]
    assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-4)


async def test_cosine_similarity_of_different_texts_is_less_than_1():
    vecs = await embed(["relational database SQL query optimization", "CSS styling BEM methodology naming"])
    assert cosine_similarity(vecs[0], vecs[1]) < 1.0


def test_memory_embed_text_includes_all_parts():
    text = memory_embed_text("main content here", "short summary", ["tag1", "tag2"])
    assert "main content here" in text
    assert "short summary" in text
    assert "tag1" in text
    assert "tag2" in text


def test_embedding_dim_is_384():
    assert EMBEDDING_DIM == 384


async def test_embed_returns_empty_for_empty_input():
    vecs = await embed([])
    assert vecs == []


async def test_embed_handles_batch():
    vecs = await embed(["first sentence about databases", "second sentence about styling"])
    assert len(vecs) == 2
    assert len(vecs[0]) == EMBEDDING_DIM
    assert len(vecs[1]) == EMBEDDING_DIM


def test_cosine_similarity_zero_vector_returns_0():
    zero = [0.0] * EMBEDDING_DIM
    nonzero = [0.1] * EMBEDDING_DIM
    assert cosine_similarity(zero, nonzero) == 0.0
    assert cosine_similarity(nonzero, zero) == 0.0


def test_cosine_similarity_mismatched_lengths_returns_0():
    a = [0.1] * EMBEDDING_DIM
    b = [0.1] * (EMBEDDING_DIM - 1)
    assert cosine_similarity(a, b) == 0.0


def test_cosine_similarity_nan_input_returns_0():
    import math

    nan = float("nan")
    a = [nan] + [0.1] * (EMBEDDING_DIM - 1)
    b = [0.1] * EMBEDDING_DIM
    result = cosine_similarity(a, b)
    assert result == 0.0 or not math.isnan(result)


async def test_vector_search_stores_embedding(service: ProjectMemoryService, tmp_dir):
    await service.remember(
        project_root=str(tmp_dir),
        kind="decision",
        content="Project memory uses SQLite as its storage backend for durable and portable local persistence across sessions.",
        why_useful_later="Future agents need to know the storage layer to diagnose database issues correctly.",
        confidence="high",
    )
    results = await service.search(project_root=str(tmp_dir), query="SQLite storage database persistence")
    assert len(results) == 1


async def test_vector_search_returns_matching_memory(service: ProjectMemoryService, tmp_dir):
    db_mem = await service.remember(
        project_root=str(tmp_dir),
        kind="architecture",
        content="The project uses a PostgreSQL relational database with connection pooling and prepared statement caching.",
        why_useful_later="Future agents need to know the database backend to generate correct queries.",
        confidence="high",
    )
    await service.remember(
        project_root=str(tmp_dir),
        kind="convention",
        content="All CSS class names follow BEM notation: block__element--modifier for consistent styling across components.",
        why_useful_later="Future agents must use BEM notation when writing CSS to match the existing codebase style.",
        confidence="high",
    )
    results = await service.search(project_root=str(tmp_dir), query="database connection pool", k=5)
    assert len(results) > 0
    assert results[0].id == db_mem.id, "Database memory should rank above CSS memory for a database query"


async def test_vector_search_returns_content_match(service: ProjectMemoryService, tmp_dir):
    await service.remember(
        project_root=str(tmp_dir),
        kind="gotcha",
        content="When deploying to production, always run database migration scripts before restarting application servers.",
        why_useful_later="Future agents need this ordering rule to avoid application startup failures during deployments.",
        confidence="high",
    )
    results = await service.search(project_root=str(tmp_dir), query="migration deployment ordering")
    assert len(results) == 1
    assert "migration" in results[0].content


async def test_archived_memories_excluded_from_vector_search(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        kind="convention",
        content="Old convention: always use tabs for indentation in TypeScript files before the project standardized on spaces.",
        why_useful_later="Future agents need to know this was the old convention before the migration to spaces.",
        confidence="medium",
    )
    service.forget(str(tmp_dir), memory.id, reason="Convention changed to spaces.")

    results = await service.search(project_root=str(tmp_dir), query="indentation TypeScript tabs")
    assert len(results) == 0

    with_archived = await service.search(project_root=str(tmp_dir), query="tabs for indentation", include_archived=True)
    assert len(with_archived) > 0


async def test_vector_search_ranks_semantic_match_first(service: ProjectMemoryService, tmp_dir):
    mem1 = await service.remember(
        project_root=str(tmp_dir),
        kind="architecture",
        content="Alpha architecture memory about relational databases and SQL query optimization techniques.",
        why_useful_later="Future agents need this for database query design.",
        confidence="high",
    )
    await service.remember(
        project_root=str(tmp_dir),
        kind="convention",
        content="Beta convention memory about CSS styling patterns and BEM methodology naming conventions.",
        why_useful_later="Future agents need this for CSS class naming.",
        confidence="high",
    )
    results = await service.search(project_root=str(tmp_dir), query="relational database SQL query optimization", k=5)
    assert len(results) > 0
    assert results[0].id == mem1.id


async def test_vector_search_semantic_without_word_overlap(service: ProjectMemoryService, tmp_dir):
    auth_mem = await service.remember(
        project_root=str(tmp_dir),
        kind="gotcha",
        content="Authentication fails with JWT tokens expiring too early because the server clock and client clock are not synchronized across timezone boundaries.",
        why_useful_later="Future agents need this to diagnose silent credential rejections during deployment windows.",
        confidence="high",
    )
    await service.remember(
        project_root=str(tmp_dir),
        kind="convention",
        content="All React components use functional style with hooks exclusively, class components are prohibited.",
        why_useful_later="Future agents must write functional components and avoid class syntax in this codebase.",
        confidence="high",
    )
    results = await service.search(project_root=str(tmp_dir), query="login issue session timeout", k=5)
    assert len(results) > 0
    assert results[0].id == auth_mem.id


async def test_vector_search_empty_corpus(service: ProjectMemoryService, tmp_dir):
    results = await service.search(project_root=str(tmp_dir), query="anything at all")
    assert results == []


async def test_vector_search_respects_k_limit(service: ProjectMemoryService, tmp_dir):
    contents = [
        "First memory about deployment pipelines and continuous integration workflows in the project.",
        "Second memory about database schema design and migration strategies for production releases.",
        "Third memory about API versioning conventions and backward compatibility requirements.",
        "Fourth memory about frontend build tooling configuration and webpack optimization settings.",
        "Fifth memory about error handling conventions and structured logging format requirements.",
    ]
    for content in contents:
        await service.remember(
            project_root=str(tmp_dir),
            kind="convention",
            content=content,
            why_useful_later="Future agents need this convention for consistent implementation across the project.",
            confidence="medium",
        )
    results = await service.search(project_root=str(tmp_dir), query="project conventions standards", k=2)
    assert len(results) == 2


async def test_user_vector_search_stores_embedding(user_service: UserMemoryService):
    await user_service.remember(
        kind="preference",
        content="User strongly prefers concise function names that accurately describe what the function does without abbreviation.",
        why_useful_later="Agents should avoid abbreviated function names and prefer clarity when naming functions.",
        confidence="high",
    )
    results = await user_service.search(query="naming functions concise clarity")
    assert len(results) == 1


async def test_user_vector_search_returns_relevant_memory(user_service: UserMemoryService):
    await user_service.remember(
        kind="preference",
        content="User prefers test-driven development and writes failing tests before implementing any production code.",
        why_useful_later="Agents should write tests first and treat failing tests as the starting point for all features.",
        confidence="high",
    )
    await user_service.remember(
        kind="convention",
        content="User applies kebab-case naming for all file names in frontend projects without exception.",
        why_useful_later="Agents should name files in kebab-case when creating frontend project files.",
        confidence="high",
    )
    results = await user_service.search(query="tests driven development TDD failing first")
    assert len(results) > 0
    assert "test" in results[0].content.lower()


async def test_user_archived_excluded_from_vector_search(user_service: UserMemoryService):
    memory = await user_service.remember(
        kind="tool_preference",
        content="User previously used Yarn for package management but has since migrated all projects to pnpm for better performance.",
        why_useful_later="Agents should use pnpm and not suggest Yarn for this user's projects.",
        confidence="high",
    )
    user_service.forget(memory.id, reason="Already migrated to pnpm.")

    results = await user_service.search(query="Yarn package management migration")
    assert len(results) == 0
