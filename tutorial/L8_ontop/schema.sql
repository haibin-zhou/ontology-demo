-- 模拟"商品中台"关系库（H2 语法）
CREATE TABLE category (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  parent_id INT REFERENCES category(id)     -- 自引用外键：类目树
);

CREATE TABLE brand (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  country VARCHAR(32)
);

CREATE TABLE merchant (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL
);

CREATE TABLE brand_authorization (
  id INT PRIMARY KEY,
  merchant_id INT NOT NULL REFERENCES merchant(id),
  brand_id INT NOT NULL REFERENCES brand(id),
  valid_until DATE NOT NULL
);

CREATE TABLE product (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  brand_id INT REFERENCES brand(id)
);

CREATE TABLE sku (
  id INT PRIMARY KEY,
  product_id INT NOT NULL REFERENCES product(id),
  category_id INT REFERENCES category(id),
  merchant_id INT REFERENCES merchant(id),
  price DECIMAL(10,2) NOT NULL,
  sales_30d INT NOT NULL,
  inventory_days INT NOT NULL,
  min_price_30d DECIMAL(10,2),
  listed_date DATE NOT NULL
);
