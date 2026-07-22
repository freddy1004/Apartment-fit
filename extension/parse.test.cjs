// Unit tests for the pure extension parser. Run: node --test extension/
const test = require("node:test");
const assert = require("node:assert");
const P = require("./parse.js");

test("num extracts numbers from messy strings", () => {
  assert.strictEqual(P.num("$1,850/mo"), 1850);
  assert.strictEqual(P.num("2.5 ba"), 2.5);
  assert.strictEqual(P.num(null), null);
});

test("parseBedBathSqft parses a summary line", () => {
  const r = P.parseBedBathSqft("3 bd | 2 ba | 1,500 sqft");
  assert.strictEqual(r.bedrooms, 3);
  assert.strictEqual(r.bathrooms, 2);
  assert.strictEqual(r.size, 1500);
});

test("parseRent finds the price", () => {
  assert.strictEqual(P.parseRent("Now renting from $2,195 a month"), 2195);
  assert.strictEqual(P.parseRent("no price here"), null);
});

test("pickAdapter matches known hosts", () => {
  assert.strictEqual(P.pickAdapter("www.zillow.com"), "zillow");
  assert.strictEqual(P.pickAdapter("www.apartments.com"), "apartments");
  assert.strictEqual(P.pickAdapter("redfin.com"), "redfin");
  assert.strictEqual(P.pickAdapter("example.org"), "generic");
});
