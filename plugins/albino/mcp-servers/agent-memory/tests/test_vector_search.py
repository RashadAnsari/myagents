"""Vector search tests: these use the real fastembed model (BAAI/bge-small-en-v1.5).
The model is downloaded on first run (~130 MB) and cached locally thereafter."""

from agent_memory.embedding import EMBEDDING_DIM, embed
from agent_memory.memory_service import ProjectMemoryService, UserMemoryService


async def test_embed_returns_correct_dim():
    vecs = await embed(["hello world"])
    assert len(vecs) == 1
    assert len(vecs[0]) == EMBEDDING_DIM


async def test_embed_same_text_is_deterministic():
    a = await embed(["hello world"])
    b = await embed(["hello world"])
    assert a[0] == b[0]


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


async def test_vector_search_stores_embedding(service: ProjectMemoryService, tmp_dir):
    await service.remember(
        project_root=str(tmp_dir),
        content="Project memory uses SQLite as its storage backend for durable and portable local persistence across sessions.",
    )
    results = await service.search(project_root=str(tmp_dir), query="SQLite storage database persistence")
    assert len(results) == 1


async def test_vector_search_returns_matching_memory(service: ProjectMemoryService, tmp_dir):
    db_mem = await service.remember(
        project_root=str(tmp_dir),
        content="The project uses a PostgreSQL relational database with connection pooling and prepared statement caching.",
    )
    await service.remember(
        project_root=str(tmp_dir),
        content="All CSS class names follow BEM notation: block__element--modifier for consistent styling across components.",
    )
    results = await service.search(project_root=str(tmp_dir), query="database connection pool", k=5)
    assert len(results) > 0
    assert results[0].id == db_mem.id, "Database memory should rank above CSS memory for a database query"


async def test_vector_search_returns_content_match(service: ProjectMemoryService, tmp_dir):
    await service.remember(
        project_root=str(tmp_dir),
        content="When deploying to production, always run database migration scripts before restarting application servers.",
    )
    results = await service.search(project_root=str(tmp_dir), query="migration deployment ordering")
    assert len(results) == 1
    assert "migration" in results[0].content


async def test_archived_memories_excluded_from_vector_search(service: ProjectMemoryService, tmp_dir):
    memory = await service.remember(
        project_root=str(tmp_dir),
        content="Old convention: always use tabs for indentation in TypeScript files before the project standardized on spaces.",
    )
    service.forget(str(tmp_dir), memory.id)

    results = await service.search(project_root=str(tmp_dir), query="indentation TypeScript tabs")
    assert len(results) == 0

    with_archived = await service.search(project_root=str(tmp_dir), query="tabs for indentation", include_archived=True)
    assert len(with_archived) > 0


async def test_vector_search_ranks_semantic_match_first(service: ProjectMemoryService, tmp_dir):
    mem1 = await service.remember(
        project_root=str(tmp_dir),
        content="Alpha architecture memory about relational databases and SQL query optimization techniques.",
    )
    await service.remember(
        project_root=str(tmp_dir),
        content="Beta convention memory about CSS styling patterns and BEM methodology naming conventions.",
    )
    results = await service.search(project_root=str(tmp_dir), query="relational database SQL query optimization", k=5)
    assert len(results) > 0
    assert results[0].id == mem1.id


async def test_vector_search_semantic_without_word_overlap(service: ProjectMemoryService, tmp_dir):
    auth_mem = await service.remember(
        project_root=str(tmp_dir),
        content="Authentication fails with JWT tokens expiring too early because the server clock and client clock are not synchronized across timezone boundaries.",
    )
    await service.remember(
        project_root=str(tmp_dir),
        content="All React components use functional style with hooks exclusively, class components are prohibited.",
    )
    results = await service.search(project_root=str(tmp_dir), query="login issue session timeout", k=5)
    assert len(results) > 0
    assert results[0].id == auth_mem.id


async def test_vector_search_returns_empty_for_unknown_project(service: ProjectMemoryService, tmp_dir):
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
        await service.remember(project_root=str(tmp_dir), content=content)
    results = await service.search(project_root=str(tmp_dir), query="project conventions standards", k=2)
    assert len(results) == 2


async def test_user_vector_search_stores_embedding(user_service: UserMemoryService):
    await user_service.remember(
        content="User strongly prefers concise function names that accurately describe what the function does without abbreviation.",
    )
    results = await user_service.search(query="naming functions concise clarity")
    assert len(results) == 1


async def test_user_vector_search_returns_relevant_memory(user_service: UserMemoryService):
    await user_service.remember(
        content="User prefers test-driven development and writes failing tests before implementing any production code.",
    )
    await user_service.remember(
        content="User applies kebab-case naming for all file names in frontend projects without exception.",
    )
    results = await user_service.search(query="tests driven development TDD failing first")
    assert len(results) > 0
    assert "test" in results[0].content.lower()


async def test_user_archived_excluded_from_vector_search(user_service: UserMemoryService):
    memory = await user_service.remember(
        content="User previously used Yarn for package management but has since migrated all projects to pnpm for better performance.",
    )
    user_service.forget(memory.id)

    results = await user_service.search(query="Yarn package management migration")
    assert len(results) == 0


GARBAGE_MEMORIES = [
    "The best pasta shapes for thick cream sauces are rigatoni and pappardelle because they hold the sauce well.",
    "Mount Everest stands at 8,849 metres above sea level and is located in the Himalayas on the Nepal-Tibet border.",
    "Wool cardigans should be hand-washed in cold water and laid flat to dry to prevent shrinkage and maintain shape.",
    "The offside rule in football is triggered when an attacker receives the ball while nearer to the goal line than both the ball and the second-to-last defender.",
    "Tomatoes thrive in full sun and need at least six hours of direct sunlight per day along with consistent watering.",
    "The boiling point of water drops by roughly 1 degree Celsius for every 300 metres of elevation gain above sea level.",
]


async def _store_garbage(service: ProjectMemoryService, tmp_dir) -> None:
    for content in GARBAGE_MEMORIES:
        await service.remember(project_root=str(tmp_dir), content=content)


async def test_search_returns_relevant_not_garbage(service: ProjectMemoryService, tmp_dir):
    """Top result for a technical query must be the on-topic memory, not one of
    the unrelated noise memories stored alongside it."""
    await _store_garbage(service, tmp_dir)
    relevant = await service.remember(
        project_root=str(tmp_dir),
        content="The API gateway uses Redis as a distributed rate-limiting backend, keyed by client IP and route prefix with a sliding-window TTL.",
    )
    results = await service.search(project_root=str(tmp_dir), query="Redis rate limiting API gateway TTL", k=1)
    assert len(results) == 1
    assert results[0].id == relevant.id, (
        f"Expected relevant memory (id={relevant.id}) to rank first, got id={results[0].id}: {results[0].content[:80]}"
    )


async def test_search_cross_domain_discrimination(service: ProjectMemoryService, tmp_dir):
    """Search must discriminate across two completely different technical domains."""
    security_mem = await service.remember(
        project_root=str(tmp_dir),
        content="All outbound HTTP requests must include an HMAC-SHA256 signature header derived from the request body and a rotating secret key to prevent replay attacks.",
    )
    styling_mem = await service.remember(
        project_root=str(tmp_dir),
        content="Design tokens for colour, spacing, and typography are defined in tokens.css and must never be duplicated inline; components import them via CSS custom properties.",
    )

    security_results = await service.search(
        project_root=str(tmp_dir), query="HMAC signature authentication replay attack prevention", k=1
    )
    assert len(security_results) == 1
    assert security_results[0].id == security_mem.id, (
        f"Security query returned styling result first: {security_results[0].content[:80]}"
    )

    styling_results = await service.search(
        project_root=str(tmp_dir), query="CSS design tokens colour spacing typography custom properties", k=1
    )
    assert len(styling_results) == 1
    assert styling_results[0].id == styling_mem.id, (
        f"Styling query returned security result first: {styling_results[0].content[:80]}"
    )


async def test_search_top_k_stays_on_topic_amid_noise(service: ProjectMemoryService, tmp_dir):
    """With many unrelated memories in the store, all top-k results for a domain
    query must come from that domain rather than from the noise pool."""
    await _store_garbage(service, tmp_dir)
    db_ids = set()
    for content in [
        "Postgres read replicas are promoted automatically by Patroni when the primary fails a health check three times in a row.",
        "Connection pool size is capped at 20 per dyno to stay within Postgres's max_connections limit of 100 across five dynos.",
        "Slow query logging is enabled at the 200 ms threshold; logs are shipped to Datadog and trigger a PagerDuty alert at 1 second.",
    ]:
        m = await service.remember(project_root=str(tmp_dir), content=content)
        db_ids.add(m.id)

    results = await service.search(project_root=str(tmp_dir), query="PostgreSQL connection pool replica failover", k=3)
    assert len(results) == 3
    returned_ids = {r.id for r in results}
    assert returned_ids == db_ids, (
        f"Expected only the 3 database memories in top-3, but got ids={returned_ids}. "
        f"Non-database result contents: {[r.content[:60] for r in results if r.id not in db_ids]}"
    )


async def test_user_search_returns_relevant_not_garbage(user_service: UserMemoryService):
    """User memory search must return the on-topic result ahead of unrelated noise."""
    noise_contents = [
        "User enjoys hiking and prefers trails with at least 500 metres of elevation gain on weekends.",
        "User collects vintage mechanical keyboards and follows several specialist forums for new arrivals.",
        "User drinks espresso in the morning and switches to herbal tea after 2 pm to avoid afternoon caffeine crashes.",
    ]
    for content in noise_contents:
        await user_service.remember(content=content)

    relevant = await user_service.remember(
        content="User always insists on structured logging with JSON output and correlation IDs on every log line so traces can be joined across services.",
    )

    results = await user_service.search(query="structured logging JSON correlation ID tracing", k=1)
    assert len(results) == 1
    assert results[0].id == relevant.id, (
        f"Expected relevant memory (id={relevant.id}), got id={results[0].id}: {results[0].content[:80]}"
    )
