def select_vector_name(
    collection: str,
    vector_length: int,
    table_query_type: str | None = None,
) -> str | None:
    if collection == "image_chunks":
        return "embedding_image" if vector_length == 768 else "embedding_caption"
    if collection == "table_chunks":
        return (
            "embedding_content"
            if table_query_type == "content"
            else "embedding_caption"
        )
    return None
