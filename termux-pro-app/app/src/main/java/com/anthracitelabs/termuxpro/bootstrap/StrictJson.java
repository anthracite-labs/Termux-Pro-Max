package com.anthracitelabs.termuxpro.bootstrap;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Small strict reader so Android and host tests reject duplicate keys alike. */
public final class StrictJson {
    private final String text;
    private int position;
    private StrictJson(String text) { this.text = text; }
    public static Object read(String text) {
        StrictJson reader = new StrictJson(text);
        Object value = reader.value(0);
        reader.space();
        check(reader.position == text.length(), "trailing JSON data");
        return value;
    }
    public static void check(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
    private void space() {
        while (position < text.length() && " \r\n\t".indexOf(text.charAt(position)) >= 0) position++;
    }
    private char next() {
        check(position < text.length(), "truncated JSON");
        return text.charAt(position++);
    }
    private Object value(int depth) {
        check(depth < 64, "JSON nesting limit");
        space();
        char c = next();
        if (c == '"') return string();
        if (c == '{') {
            Map<String, Object> result = new LinkedHashMap<>();
            space();
            if (position < text.length() && text.charAt(position) == '}') { position++; return result; }
            do {
                space(); check(next() == '"', "expected JSON object key");
                String key = string();
                check(!result.containsKey(key), "duplicate JSON key: " + key);
                space(); check(next() == ':', "expected JSON colon");
                result.put(key, value(depth + 1));
                space(); c = next();
                if (c == '}') return result;
                check(c == ',', "expected JSON comma");
            } while (true);
        }
        if (c == '[') {
            List<Object> result = new ArrayList<>();
            space();
            if (position < text.length() && text.charAt(position) == ']') { position++; return result; }
            do {
                result.add(value(depth + 1));
                space(); c = next();
                if (c == ']') return result;
                check(c == ',', "expected JSON comma");
            } while (true);
        }
        position--;
        for (String literal : new String[]{"true", "false", "null"}) {
            if (text.startsWith(literal, position)) {
                position += literal.length();
                return literal.equals("null") ? null : literal.equals("true");
            }
        }
        int start = position;
        while (position < text.length() && "0123456789+-.eE".indexOf(text.charAt(position)) >= 0) position++;
        String number = text.substring(start, position);
        check(number.matches("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?"), "invalid JSON value");
        try {
            if (number.indexOf('.') < 0 && number.indexOf('e') < 0 && number.indexOf('E') < 0) return Long.valueOf(number);
            double value = Double.parseDouble(number);
            check(!Double.isInfinite(value) && !Double.isNaN(value), "invalid JSON number");
            return value;
        } catch (NumberFormatException error) { throw new IllegalArgumentException("JSON number out of range", error); }
    }
    private String string() {
        StringBuilder result = new StringBuilder();
        for (;;) {
            char c = next();
            if (c == '"') return result.toString();
            check(c >= 32, "control character in JSON string");
            if (c == '\\') {
                c = next();
                switch (c) {
                    case '"': case '\\': case '/': break;
                    case 'b': c = '\b'; break;
                    case 'f': c = '\f'; break;
                    case 'n': c = '\n'; break;
                    case 'r': c = '\r'; break;
                    case 't': c = '\t'; break;
                    case 'u':
                        int value = 0;
                        for (int i = 0; i < 4; i++) {
                            int digit = Character.digit(next(), 16);
                            check(digit >= 0, "invalid JSON unicode escape");
                            value = value * 16 + digit;
                        }
                        c = (char) value;
                        break;
                    default: throw new IllegalArgumentException("invalid JSON escape");
                }
            }
            result.append(c);
        }
    }
}
