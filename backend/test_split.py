def _recursive_split(content: str, max_size: int, overlap: int) -> list[tuple[str, str]]:
    if not content:
        return []
    if len(content) <= max_size:
        return [("", content.strip())]

    chunks = []
    start = 0
    while start < len(content):
        end = min(start + max_size, len(content))
        if end < len(content):
            boundary = content.rfind("\n\n", start, end)
            if boundary > start + overlap:
                end = boundary
        
        chunk_text = content[start:end].strip()
        if chunk_text:
            chunks.append(("", chunk_text))
            
        if end >= len(content):
            print(f"End reached: {end} >= {len(content)}")
            break
            
        start = end - overlap
        print(f"Next start: {start}")
    return chunks

content = "A" * 780
print(f"Testing with length {len(content)}")
res = _recursive_split(content, 800, 200)
print(f"Result len: {len(res)}")
