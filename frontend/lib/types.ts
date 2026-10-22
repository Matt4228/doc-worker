/** GET /documents/{id}: metadata plus extracted text, never the file bytes. */
export interface DocumentDetail {
    id: string;
    filename: string;
    created_at: string;
    content_type: string | null;
    /** Whether the original PDF is stored and can be rendered. */
    has_file: boolean;
    /** Extracted text, shown when there's no file to render. */
    content: string;
}
