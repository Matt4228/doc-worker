import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// react-markdown never renders raw HTML from the model's output (that would
// need rehype-raw), and its default URL transform drops javascript: links,
// so model text can't inject markup or script into the page.
const components: Components = {
    a: ({ href, children }) => (
        <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
        </a>
    ),
    // Wide tables scroll inside the chat pane instead of widening it.
    table: ({ children }) => (
        <div className="overflow-x-auto">
            <table>{children}</table>
        </div>
    ),
};

export default function Markdown({ children }: { children: string }) {
    return (
        <div
            className="prose prose-invert prose-sm max-w-none
                prose-headings:font-semibold prose-headings:text-gray-100
                prose-h1:text-base prose-h2:text-base prose-h3:text-sm
                prose-p:leading-relaxed prose-li:my-0.5
                prose-a:text-blue-400 prose-a:underline-offset-2
                prose-strong:text-gray-100
                prose-code:rounded prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:font-normal
                prose-code:before:content-none prose-code:after:content-none
                prose-pre:border prose-pre:border-gray-800 prose-pre:bg-gray-900
                prose-th:text-gray-200 prose-td:text-gray-300"
        >
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {children}
            </ReactMarkdown>
        </div>
    );
}
