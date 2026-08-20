"""
Semantic chunker for resumes and career documents.

Why semantic over fixed-size:
- Resumes have natural boundaries (sections: Experience, Education, Skills)
- Fixed-size chunking can split a bullet point from its context
- We want each chunk to be a coherent, self-contained unit

Interview line: "I chunked by resume section rather than fixed token windows
because splitting mid-bullet-point would separate an achievement from its metric,
hurting retrieval precision."
"""

import re
from typing import List
from dataclasses import dataclass


@dataclass
class Chunk:
    """A single retrievable piece of content."""
    content: str
    metadata: dict  # {section, company, dates, etc.}


class ResumeChunker:
    """
    Chunks resume text into retrievable units based on document structure.

    Strategy:
    1. Split by major sections (Experience, Education, Skills, etc.)
    2. Within Experience, split by company/role
    3. For long entries, sub-chunk while preserving context
    """

    # Common resume section headers (case-insensitive matching)
    SECTION_PATTERNS = [
        r"^experience\s*$",
        r"^work\s*experience\s*$",
        r"^professional\s*experience\s*$",
        r"^education\s*$",
        r"^skills\s*$",
        r"^technical\s*skills\s*$",
        r"^projects\s*$",
        r"^publications\s*$",
        r"^certifications\s*$",
        r"^awards\s*$",
        r"^summary\s*$",
        r"^objective\s*$",
        r"^languages\s*$",
        r"^interests\s*$",
    ]

    # Compiled pattern for section detection
    SECTION_REGEX = re.compile(
        r"^(?:{0})".format("|".join(SECTION_PATTERNS)),
        re.IGNORECASE | re.MULTILINE
    )

    # Pattern for company/role entries (often: Company Name | Role | Dates)
    ENTRY_PATTERN = re.compile(
        r"^(.+?)\s*[\|–—-]\s*(.+?)\s*[\|–—-]?\s*(.+?)$",
        re.MULTILINE
    )

    def __init__(self, max_chunk_size: int = 1000, min_chunk_size: int = 100):
        """
        Initialize the chunker.

        Args:
            max_chunk_size: Maximum characters per chunk (not tokens)
            min_chunk_size: Minimum characters to create a separate chunk
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def _detect_sections(self, text: str) -> List[dict]:
        """
        Detect section boundaries in the resume text.

        Returns:
            List of dicts with {section_name, start, end, content}
        """
        sections = []
        matches = list(self.SECTION_REGEX.finditer(text))

        for i, match in enumerate(matches):
            section_name = match.group(0).strip()
            start = match.end()

            # End is the start of next section, or end of text
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)

            content = text[start:end].strip()
            if content:
                sections.append({
                    "name": section_name.lower().replace(" ", "_"),
                    "start": start,
                    "end": end,
                    "content": content
                })

        # If no sections found, treat entire document as one section
        if not sections and text.strip():
            sections.append({
                "name": "unknown",
                "start": 0,
                "end": len(text),
                "content": text.strip()
            })

        return sections

    def _chunk_experience_section(self, content: str) -> List[Chunk]:
        """
        Chunk an Experience section by role/company.

        Experience entries typically follow patterns like:
        - Company Name, City | Role | Dates
        - Role at Company (Dates)
        - Company Name (Month Year - Month Year)

        We try to detect these boundaries and keep each role together.
        """
        chunks = []

        # Split by blank lines (often separate entries)
        entries = re.split(r"\n\s*\n", content)

        current_chunk = []
        current_length = 0
        current_company = None

        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            # Try to extract company name from entry header
            first_line = entry.split("\n")[0]
            company_match = re.match(r"^([^|–—,\n]+)", first_line)
            if company_match:
                potential_company = company_match.group(1).strip()
                # Check if this looks like a new entry (new company)
                if potential_company and potential_company != current_company:
                    # Save previous chunk if exists
                    if current_chunk:
                        chunk_content = "\n\n".join(current_chunk)
                        chunks.append(Chunk(
                            content=chunk_content,
                            metadata={
                                "section": "experience",
                                "company": current_company
                            }
                        ))
                        current_chunk = []
                        current_length = 0
                    current_company = potential_company

            # Add entry to current chunk
            if current_length + len(entry) > self.max_chunk_size and current_chunk:
                # Save current chunk and start new one
                chunk_content = "\n\n".join(current_chunk)
                chunks.append(Chunk(
                    content=chunk_content,
                    metadata={
                        "section": "experience",
                        "company": current_company
                    }
                ))
                current_chunk = [entry]
                current_length = len(entry)
            else:
                current_chunk.append(entry)
                current_length += len(entry)

        # Don't forget the last chunk
        if current_chunk:
            chunk_content = "\n\n".join(current_chunk)
            chunks.append(Chunk(
                content=chunk_content,
                metadata={
                    "section": "experience",
                    "company": current_company
                }
            ))

        return chunks

    def _chunk_skills_section(self, content: str) -> List[Chunk]:
        """
        Chunk skills section - usually a list or categorized skills.

        Keep all skills together if reasonable size, otherwise split by category.
        """
        # If the whole section fits, return as one chunk
        if len(content) <= self.max_chunk_size:
            return [Chunk(
                content=content,
                metadata={"section": "skills"}
            )]

        # Otherwise, split by category (often delimited by colons or newlines)
        chunks = []
        # Pattern: "Category: skill1, skill2, skill3"
        category_pattern = re.compile(r"^([^:\n]+):\s*", re.MULTILINE)
        matches = list(category_pattern.finditer(content))

        if matches:
            for i, match in enumerate(matches):
                category = match.group(1).strip()
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                skill_content = content[start:end].strip()

                if len(skill_content) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        content=f"{category}: {skill_content}",
                        metadata={"section": "skills", "category": category}
                    ))
        else:
            # No clear categories, just split by size
            for i in range(0, len(content), self.max_chunk_size):
                chunks.append(Chunk(
                    content=content[i:i + self.max_chunk_size],
                    metadata={"section": "skills"}
                ))

        return chunks

    def _chunk_generic_section(self, section_name: str, content: str) -> List[Chunk]:
        """
        Generic chunking for any section type.
        Splits by paragraphs, respecting size limits.
        """
        chunks = []

        if len(content) <= self.max_chunk_size:
            return [Chunk(
                content=content,
                metadata={"section": section_name}
            )]

        # Split by paragraphs
        paragraphs = re.split(r"\n\s*\n", content)
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_length + len(para) > self.max_chunk_size and current_chunk:
                # Save current chunk
                chunks.append(Chunk(
                    content="\n\n".join(current_chunk),
                    metadata={"section": section_name}
                ))
                current_chunk = [para]
                current_length = len(para)
            else:
                current_chunk.append(para)
                current_length += len(para)

        if current_chunk:
            chunks.append(Chunk(
                content="\n\n".join(current_chunk),
                metadata={"section": section_name}
            ))

        return chunks

    def chunk(self, text: str) -> List[Chunk]:
        """
        Main entry point - chunk resume text into retrievable units.

        Args:
            text: Full resume text

        Returns:
            List of Chunk objects with content and metadata
        """
        all_chunks = []
        sections = self._detect_sections(text)

        for section in sections:
            section_name = section["name"]
            content = section["content"]

            if "experience" in section_name:
                section_chunks = self._chunk_experience_section(content)
            elif "skill" in section_name:
                section_chunks = self._chunk_skills_section(content)
            else:
                section_chunks = self._chunk_generic_section(section_name, content)

            all_chunks.extend(section_chunks)

        return all_chunks


def chunk_document(text: str, doc_type: str = "resume") -> List[Chunk]:
    """
    Main function to chunk any document type.

    Args:
        text: Document text
        doc_type: Type of document (resume, project, cover_letter, etc.)

    Returns:
        List of Chunk objects
    """
    if doc_type == "resume":
        chunker = ResumeChunker()
        return chunker.chunk(text)
    else:
        # Generic chunking for other document types
        chunker = ResumeChunker()  # Reuse logic
        return chunker._chunk_generic_section(doc_type, text)
